/*
 * sandbox gate for Android/Termux: advisory write confinement via LD_PRELOAD.
 *
 * Android's GKI kernels ship without Landlock (create_ruleset returns ENOSYS
 * on android14-6.1) and deny unprivileged user namespaces, so neither the
 * Landlock gate nor bwrap can run. One C source builds two artifacts:
 *
 *   launcher   cc -std=c99 -o gate gate-preload.c
 *       Parses the same contract as gate.c (--ws, --allow, -- <argv>), exports
 *       the policy as PI_GATE_* environment variables, prepends the
 *       interposer to LD_PRELOAD and execs the command. Fails closed when the
 *       interposer is missing.
 *
 *   interposer cc -shared -fPIC -DPI_GATE_LIB -o gate-preload.so gate-preload.c
 *       Hooks the libc write family (open/openat/creat, fopen/freopen,
 *       rename/renameat/renameat2, unlink/unlinkat/remove, mkdir/mkdirat,
 *       rmdir, link/linkat, symlink/symlinkat, mkfifo/mkfifoat, mknod/mknodat,
 *       truncate, chmod/fchmodat, chown/lchown/fchownat, utimensat/utimes/
 *       lutimes, mkstemp/mkstemps, faccessat W_OK) and denies anything
 *       outside the policy with EACCES. Reads are never hooked.
 *
 * Advisory by nature: interposition happens in libc's PLT, so a program that
 * issues raw syscalls (inline asm, a static binary) bypasses it. That is the
 * same trust tier as the Windows low-integrity backend. Paths are resolved
 * through realpath so a symlink inside the grant cannot escape it; dirfd-
 * relative paths resolve through /proc/self/fd. A missing or unparsable
 * policy denies every write — fail closed, like the other backends.
 */

#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ENV_WS "PI_GATE_WS"
#define ENV_ALLOW "PI_GATE_ALLOW"
#define ENV_TMP "PI_GATE_TMP"
#define LIB_NAME "gate-preload.so"

#ifndef PI_GATE_LIB
/* ── Launcher ──────────────────────────────────────────────────────────── */

int main(int argc, char **argv) {
	const char *ws = NULL;
	const char *allows[64];
	int nallows = 0;
	const char *tmp = NULL;
	int i = 1;
	while (i < argc) {
		if (strcmp(argv[i], "--ws") == 0 && i + 1 < argc) {
			ws = argv[++i];
			i++;
		} else if (strcmp(argv[i], "--allow") == 0 && i + 1 < argc) {
			if (nallows < 64) allows[nallows++] = argv[++i];
			i++;
		} else if (strcmp(argv[i], "--tmp") == 0 && i + 1 < argc) {
			tmp = argv[++i];
			i++;
		} else if (strcmp(argv[i], "--") == 0) {
			i++;
			break;
		} else {
			fprintf(stderr, "sandbox: unexpected argument \"%s\"\n", argv[i]);
			return 126;
		}
	}
	if (!ws) {
		fprintf(stderr, "sandbox: missing --ws\n");
		return 126;
	}
	if (i >= argc) {
		fprintf(stderr, "sandbox: no command to run\n");
		return 126;
	}

	/* Resolve the workspace to an absolute path (same rule as gate.c). */
	char wsbuf[PATH_MAX];
	const char *wsabs = ws;
	if (ws[0] != '/') {
		if (getcwd(wsbuf, sizeof wsbuf) == NULL) {
			perror("sandbox: getcwd");
			return 126;
		}
		if (strcmp(ws, ".") != 0) {
			size_t l = strlen(wsbuf);
			if (l + 1 + strlen(ws) >= sizeof wsbuf) {
				fprintf(stderr, "sandbox: workspace path too long\n");
				return 126;
			}
			if (wsbuf[l - 1] != '/') {
				wsbuf[l++] = '/';
				wsbuf[l] = '\0';
			}
			strncat(wsbuf, ws, sizeof wsbuf - l - 1);
		}
		wsabs = wsbuf;
	}

	/* The interposer lives next to the launcher in the cache directory. */
	char lib[PATH_MAX];
	char dirbuf[PATH_MAX];
	snprintf(dirbuf, sizeof dirbuf, "%s", argv[0]);
	char *slash = strrchr(dirbuf, '/');
	if (slash) *slash = '\0'; else strcpy(dirbuf, ".");
	snprintf(lib, sizeof lib, "%s/%s", dirbuf, LIB_NAME);
	if (access(lib, R_OK) != 0) {
		fprintf(stderr, "sandbox: interposer missing (%s): %s — refusing to run unconfined\n",
			lib, strerror(errno));
		return 125;
	}

	if (setenv(ENV_WS, wsabs, 1) != 0) {
		perror("sandbox: setenv(" ENV_WS ")");
		return 126;
	}
	/* Paths are joined with \n: the list travels in one variable and paths
	 * with newlines are pathological enough to exclude. */
	size_t cap = (size_t)nallows * PATH_MAX + (tmp ? PATH_MAX : 0) + 1;
	char *list = malloc(cap);
	if (!list) {
		perror("sandbox: malloc");
		return 126;
	}
	list[0] = '\0';
	for (int j = 0; j < nallows; j++) {
		if (j > 0) strncat(list, "\n", cap - strlen(list) - 1);
		strncat(list, allows[j], cap - strlen(list) - 1);
	}
	if (tmp) {
		if (nallows > 0) strncat(list, "\n", cap - strlen(list) - 1);
		strncat(list, tmp, cap - strlen(list) - 1);
	}
	if (*list && setenv(ENV_ALLOW, list, 1) != 0) {
		perror("sandbox: setenv(" ENV_ALLOW ")");
		free(list);
		return 126;
	}
	free(list);
	if (tmp && setenv(ENV_TMP, tmp, 1) != 0) {
		perror("sandbox: setenv(" ENV_TMP ")");
		return 126;
	}

	/* Prepend, unless the interposer is already loaded (nested gates). */
	const char *cur = getenv("LD_PRELOAD");
	if (!cur || !strstr(cur, LIB_NAME)) {
		char pre[PATH_MAX * 2];
		snprintf(pre, sizeof pre, "%s%s%s", lib, (cur && *cur) ? ":" : "", (cur && *cur) ? cur : "");
		if (setenv("LD_PRELOAD", pre, 1) != 0) {
			perror("sandbox: setenv(LD_PRELOAD)");
			return 126;
		}
	}

	execvp(argv[i], &argv[i]);
	perror("sandbox: exec");
	return 127;
}

#else
/* ── Interposer ────────────────────────────────────────────────────────── */

#include <pthread.h>
#include <sys/stat.h>
#include <sys/types.h>

static char **g_prefixes;
static int g_nprefixes;
static pthread_once_t g_once = PTHREAD_ONCE_INIT;

static void add_prefix(const char *path) {
	if (!path || !*path) return;
	char **re = realloc(g_prefixes, ((size_t)g_nprefixes + 1) * sizeof *re);
	if (!re) return;
	g_prefixes = re;
	g_prefixes[g_nprefixes] = strdup(path);
	if (g_prefixes[g_nprefixes]) g_nprefixes++;
}

static void load_policy(void) {
	const char *ws = getenv(ENV_WS);
	if (!ws || !*ws) return; /* no policy: deny everything (fail closed) */
	add_prefix(ws);
	const char *allow = getenv(ENV_ALLOW);
	if (allow) {
		const char *p = allow;
		while (*p) {
			const char *nl = strchr(p, '\n');
			size_t len = nl ? (size_t)(nl - p) : strlen(p);
			if (len > 0) {
				char piece[PATH_MAX];
				if (len < sizeof piece) {
					memcpy(piece, p, len);
					piece[len] = '\0';
					add_prefix(piece);
				}
			}
			p += len;
			if (!nl) break;
			p++;
		}
	}
}

/** Exact-prefix match with a path boundary: /a/b never grants /a/bc. */
static int is_allowed(const char *abs) {
	for (int i = 0; i < g_nprefixes; i++) {
		size_t len = strlen(g_prefixes[i]);
		if (strncmp(abs, g_prefixes[i], len) == 0 && (abs[len] == '\0' || abs[len] == '/')) {
			return 1;
		}
	}
	return 0;
}

/* Resolve one final component against a realpath'd directory. */
static int resolve_parent(const char *abs, char *out, size_t outlen) {
	char parent[PATH_MAX];
	snprintf(parent, sizeof parent, "%s", abs);
	char *slash = strrchr(parent, '/');
	if (!slash) return -1;
	const char *base = slash + 1;
	if (slash == parent) parent[1] = '\0'; /* "/" */
	else *slash = '\0';
	char real[PATH_MAX];
	if (realpath(parent, real) == NULL) return -1;
	int n = snprintf(out, outlen, "%s%s%s", real,
		strlen(real) == 1 ? "" : "/", base);
	return (n > 0 && (size_t)n < outlen) ? 0 : -1;
}

/**
 * Decide a write to `path` (dirfd-relative for the *at family). Returns 1 to
 * allow, 0 to deny with EACCES. Denies on every resolution failure.
 */
static int decide(const char *path, int dirfd) {
	pthread_once(&g_once, load_policy);
	if (!path || !*path) return 0;
	char joined[PATH_MAX];
	const char *abs = path;
	if (path[0] != '/') {
		char base[PATH_MAX];
		if (dirfd == AT_FDCWD || dirfd < 0) {
			if (!getcwd(base, sizeof base)) return 0;
		} else {
			char fdlink[64];
			snprintf(fdlink, sizeof fdlink, "/proc/self/fd/%d", dirfd);
			ssize_t n = readlink(fdlink, base, sizeof base - 1);
			if (n <= 0) return 0;
			base[n] = '\0';
		}
		if (snprintf(joined, sizeof joined, "%s/%s", base, path) >= (int)sizeof joined) return 0;
		abs = joined;
	}
	char real[PATH_MAX];
	if (realpath(abs, real) == NULL && errno == ENOENT) {
		if (resolve_parent(abs, real, sizeof real) != 0) return 0;
	} else if (realpath(abs, real) == NULL) {
		return 0;
	}
	return is_allowed(real);
}

#define DENY() do { errno = EACCES; return -1; } while (0)
#define REAL(name) static __typeof__(name) *real_##name
#define LOAD(name) if (!real_##name && !(real_##name = (__typeof__(name) *)dlsym(RTLD_NEXT, #name)))

static int write_flags(int f) {
	if (f & (O_WRONLY | O_RDWR | O_TRUNC | O_CREAT | O_APPEND)) return 1;
#ifdef O_TMPFILE
	if (f & O_TMPFILE) return 1;
#endif
	return 0;
}

/* ── open family ── */
REAL(open);
int open(const char *path, int flags, ...) {
	mode_t mode = 0;
	if (flags & O_CREAT) {
		va_list ap;
		va_start(ap, flags);
		mode = va_arg(ap, int);
		va_end(ap);
	}
	LOAD(open) DENY();
	if (write_flags(flags) && !decide(path, AT_FDCWD)) DENY();
	if (flags & O_CREAT) return real_open(path, flags, mode);
	return real_open(path, flags);
}

REAL(openat);
int openat(int dirfd, const char *path, int flags, ...) {
	mode_t mode = 0;
	if (flags & O_CREAT) {
		va_list ap;
		va_start(ap, flags);
		mode = va_arg(ap, int);
		va_end(ap);
	}
	LOAD(openat) DENY();
	if (write_flags(flags) && !decide(path, dirfd)) DENY();
	if (flags & O_CREAT) return real_openat(dirfd, path, flags, mode);
	return real_openat(dirfd, path, flags);
}

REAL(creat);
int creat(const char *path, mode_t mode) {
	LOAD(creat) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_creat(path, mode);
}

/* ── stdio ── */
static int write_mode(const char *mode) { return mode && strpbrk(mode, "wa+"); }

REAL(fopen);
FILE *fopen(const char *path, const char *mode) {
	LOAD(fopen) { errno = EACCES; return NULL; }
	if (write_mode(mode) && !decide(path, AT_FDCWD)) { errno = EACCES; return NULL; }
	return real_fopen(path, mode);
}

REAL(freopen);
FILE *freopen(const char *path, const char *mode, FILE *stream) {
	LOAD(freopen) { errno = EACCES; return NULL; }
	if (write_mode(mode) && !decide(path, AT_FDCWD)) { errno = EACCES; return NULL; }
	return real_freopen(path, mode, stream);
}

/* ── delete / move ── */
REAL(unlink);
int unlink(const char *path) {
	LOAD(unlink) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_unlink(path);
}

REAL(unlinkat);
int unlinkat(int dirfd, const char *path, int flags) {
	LOAD(unlinkat) DENY();
	if (!decide(path, dirfd)) DENY();
	return real_unlinkat(dirfd, path, flags);
}

REAL(remove);
int remove(const char *path) {
	LOAD(remove) { errno = EACCES; return -1; }
	if (!decide(path, AT_FDCWD)) { errno = EACCES; return -1; }
	return real_remove(path);
}

REAL(rename);
int rename(const char *old, const char *new) {
	LOAD(rename) DENY();
	if (!decide(old, AT_FDCWD) || !decide(new, AT_FDCWD)) DENY();
	return real_rename(old, new);
}

REAL(renameat);
int renameat(int oldfd, const char *old, int newfd, const char *new) {
	LOAD(renameat) DENY();
	if (!decide(old, oldfd) || !decide(new, newfd)) DENY();
	return real_renameat(oldfd, old, newfd, new);
}

#ifdef RENAME_EXCHANGE
REAL(renameat2);
int renameat2(int oldfd, const char *old, int newfd, const char *new, int flags) {
	LOAD(renameat2) DENY();
	if (!decide(old, oldfd) || !decide(new, newfd)) DENY();
	return real_renameat2(oldfd, old, newfd, new, flags);
}
#endif

/* ── make ── */
REAL(mkdir);
int mkdir(const char *path, mode_t mode) {
	LOAD(mkdir) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_mkdir(path, mode);
}

REAL(mkdirat);
int mkdirat(int dirfd, const char *path, mode_t mode) {
	LOAD(mkdirat) DENY();
	if (!decide(path, dirfd)) DENY();
	return real_mkdirat(dirfd, path, mode);
}

REAL(rmdir);
int rmdir(const char *path) {
	LOAD(rmdir) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_rmdir(path);
}

REAL(link);
int link(const char *old, const char *new) {
	LOAD(link) DENY();
	if (!decide(old, AT_FDCWD) || !decide(new, AT_FDCWD)) DENY();
	return real_link(old, new);
}

REAL(linkat);
int linkat(int oldfd, const char *old, int newfd, const char *new, int flags) {
	LOAD(linkat) DENY();
	if (!decide(old, oldfd) || !decide(new, newfd)) DENY();
	return real_linkat(oldfd, old, newfd, new, flags);
}

REAL(symlink);
int symlink(const char *target, const char *linkpath) {
	LOAD(symlink) DENY();
	/* The target is interpreted at use time; only the link location writes. */
	if (!decide(linkpath, AT_FDCWD)) DENY();
	return real_symlink(target, linkpath);
}

REAL(symlinkat);
int symlinkat(const char *target, int newfd, const char *linkpath) {
	LOAD(symlinkat) DENY();
	if (!decide(linkpath, newfd)) DENY();
	return real_symlinkat(target, newfd, linkpath);
}

REAL(mkfifo);
int mkfifo(const char *path, mode_t mode) {
	LOAD(mkfifo) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_mkfifo(path, mode);
}

REAL(mkfifoat);
int mkfifoat(int dirfd, const char *path, mode_t mode) {
	LOAD(mkfifoat) DENY();
	if (!decide(path, dirfd)) DENY();
	return real_mkfifoat(dirfd, path, mode);
}

REAL(mknod);
int mknod(const char *path, mode_t mode, dev_t dev) {
	LOAD(mknod) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_mknod(path, mode, dev);
}

REAL(mknodat);
int mknodat(int dirfd, const char *path, mode_t mode, dev_t dev) {
	LOAD(mknodat) DENY();
	if (!decide(path, dirfd)) DENY();
	return real_mknodat(dirfd, path, mode, dev);
}

REAL(mkstemp);
int mkstemp(char *template) {
	LOAD(mkstemp) DENY();
	if (!decide(template, AT_FDCWD)) DENY();
	return real_mkstemp(template);
}

REAL(mkstemps);
int mkstemps(char *template, int suffixlen) {
	LOAD(mkstemps) DENY();
	if (!decide(template, AT_FDCWD)) DENY();
	return real_mkstemps(template, suffixlen);
}

/* ── metadata ── */
REAL(truncate);
int truncate(const char *path, off_t length) {
	LOAD(truncate) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_truncate(path, length);
}

REAL(chmod);
int chmod(const char *path, mode_t mode) {
	LOAD(chmod) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_chmod(path, mode);
}

REAL(fchmodat);
int fchmodat(int dirfd, const char *path, mode_t mode, int flags) {
	LOAD(fchmodat) DENY();
	if (!decide(path, dirfd)) DENY();
	return real_fchmodat(dirfd, path, mode, flags);
}

REAL(chown);
int chown(const char *path, uid_t owner, gid_t group) {
	LOAD(chown) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_chown(path, owner, group);
}

REAL(lchown);
int lchown(const char *path, uid_t owner, gid_t group) {
	LOAD(lchown) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_lchown(path, owner, group);
}

REAL(fchownat);
int fchownat(int dirfd, const char *path, uid_t owner, gid_t group, int flags) {
	LOAD(fchownat) DENY();
	if (!decide(path, dirfd)) DENY();
	return real_fchownat(dirfd, path, owner, group, flags);
}

#include <sys/time.h>

REAL(utimensat);
int utimensat(int dirfd, const char *path, const struct timespec times[2], int flags) {
	LOAD(utimensat) DENY();
	if (path && !decide(path, dirfd)) DENY();
	return real_utimensat(dirfd, path, times, flags);
}

REAL(utimes);
int utimes(const char *path, const struct timeval times[2]) {
	LOAD(utimes) DENY();
	if (!decide(path, AT_FDCWD)) DENY();
	return real_utimes(path, times);
}
/* lutimes: absent from bionic; utimensat(AT_SYMLINK_NOFOLLOW) covers the case. */

/* ── probes: keep `test -w` honest outside the grant ── */
REAL(faccessat);
int faccessat(int dirfd, const char *path, int amode, int flags) {
	LOAD(faccessat) DENY();
	if ((amode & W_OK) && !decide(path, dirfd)) DENY();
	return real_faccessat(dirfd, path, amode, flags);
}

#endif /* PI_GATE_LIB */
