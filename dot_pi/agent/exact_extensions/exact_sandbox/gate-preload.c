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
#include <sys/ioctl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#define ENV_WS "PI_GATE_WS"
#define ENV_ALLOW "PI_GATE_ALLOW"
#define ENV_TMP "PI_GATE_TMP"
#define LIB_NAME "gate-preload.so"




#ifndef PI_GATE_LIB
/* ── Launcher ──────────────────────────────────────────────────────────── */

/*
 * Kernel-enforced backstop: deny the syscall mechanisms no libc interposer
 * can see — io_uring (kernel-side file writes without libc), mount and
 * namespace manipulation, module and keyring loading, ptrace, kexec, bpf,
 * perf. A filter denies syscall *numbers*, never paths, so this cannot
 * replace the interposer; it closes the exotic routes around it. Best
 * effort: if the kernel refuses the filter the interposer still applies.
 */
static void install_seccomp_backstop(void) {
	struct sock_filter prog[] = {
		{ .code = BPF_LD | BPF_W | BPF_ABS, .jt = 0, .jf = 0, .k = 0 },
#define DENY_NR(nr) \
		{ .code = BPF_JMP | BPF_JEQ | BPF_K, .jt = 1, .jf = 0, .k = (nr) },
#ifdef SYS_io_uring_setup
		DENY_NR(SYS_io_uring_setup)
#endif
#ifdef SYS_io_uring_enter
		DENY_NR(SYS_io_uring_enter)
#endif
#ifdef SYS_io_uring_register
		DENY_NR(SYS_io_uring_register)
#endif
#ifdef SYS_mount
		DENY_NR(SYS_mount)
#endif
#ifdef SYS_umount2
		DENY_NR(SYS_umount2)
#endif
#ifdef SYS_pivot_root
		DENY_NR(SYS_pivot_root)
#endif
#ifdef SYS_swapon
		DENY_NR(SYS_swapon)
#endif
#ifdef SYS_swapoff
		DENY_NR(SYS_swapoff)
#endif
#ifdef SYS_reboot
		DENY_NR(SYS_reboot)
#endif
#ifdef SYS_kexec_load
		DENY_NR(SYS_kexec_load)
#endif
#ifdef SYS_kexec_file_load
		DENY_NR(SYS_kexec_file_load)
#endif
#ifdef SYS_init_module
		DENY_NR(SYS_init_module)
#endif
#ifdef SYS_finit_module
		DENY_NR(SYS_finit_module)
#endif
#ifdef SYS_delete_module
		DENY_NR(SYS_delete_module)
#endif
#ifdef SYS_bpf
		DENY_NR(SYS_bpf)
#endif
#ifdef SYS_ptrace
		DENY_NR(SYS_ptrace)
#endif
#ifdef SYS_keyctl
		DENY_NR(SYS_keyctl)
#endif
#ifdef SYS_add_key
		DENY_NR(SYS_add_key)
#endif
#ifdef SYS_request_key
		DENY_NR(SYS_request_key)
#endif
#ifdef SYS_perf_event_open
		DENY_NR(SYS_perf_event_open)
#endif
#ifdef SYS_setns
		DENY_NR(SYS_setns)
#endif
#ifdef SYS_open_by_handle_at
		DENY_NR(SYS_open_by_handle_at)
#endif
		{ .code = BPF_RET | BPF_K, .jt = 0, .jf = 0, .k = SECCOMP_RET_ALLOW },
		{ .code = BPF_RET | BPF_K, .jt = 0, .jf = 0, .k = SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA) },
	};
	struct sock_fprog fprog = {
		.len = (unsigned short)(sizeof prog / sizeof prog[0]),
		.filter = prog,
	};
	if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) return;
	if (syscall(SYS_seccomp, SECCOMP_SET_MODE_FILTER, 0, &fprog) != 0) {
		fprintf(stderr, "sandbox: seccomp backstop unavailable: %s\n", strerror(errno));
	}
}

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
	/* Always overwrite: a nested gate (pi's own session wrapping a command
	 * that runs gate again) inherits the parent's PI_GATE_* otherwise, and
	 * the inner grant would silently widen to the outer's. */
	if (setenv(ENV_ALLOW, list, 1) != 0) {
		perror("sandbox: setenv(" ENV_ALLOW ")");
		free(list);
		return 126;
	}
	free(list);
	if (setenv(ENV_TMP, tmp ? tmp : "", 1) != 0) {
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

	/* Deny the exotic kernel interfaces before the command ever runs. */
	install_seccomp_backstop();

	execvp(argv[i], &argv[i]);
	perror("sandbox: exec");
	return 127;
}

#else
/* ── Interposer ────────────────────────────────────────────────────────── */

#include <pthread.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <sys/types.h>

static char **g_prefixes;
static int g_nprefixes;
static pthread_once_t g_once = PTHREAD_ONCE_INIT;

static void add_prefix(const char *path) {
	if (!path || !*path) return;
	/* Grant roots are normalized through realpath so a symlinked root (like
	 * Termux's /tmp -> usr/tmp) grants the directory it names, matching how
	 * decide() evaluates written paths. Unresolvable roots stay as written. */
	char real[PATH_MAX];
	const char *granted = realpath(path, real) ? real : path;
	char **re = realloc(g_prefixes, ((size_t)g_nprefixes + 1) * sizeof *re);
	if (!re) return;
	g_prefixes = re;
	g_prefixes[g_nprefixes] = strdup(granted);
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
 * Decide a write to `path` (dirfd-relative for the *at family). `follow`
 * selects symlink semantics: a write THROUGH the final component (open,
 * chmod…) judges its target; a write TO the directory entry itself (unlink,
 * rename's old side, rmdir) judges the entry's parent — Landlock's REMOVE
 * semantics, and what makes a workspace symlink to an outside path creatable
 * and removable.
 */
/** Deny with EACCES, optionally explaining why (PI_GATE_DEBUG=1). */
static int deny_op(const char *op, const char *path) {
	if (getenv("PI_GATE_DEBUG") != NULL) {
		fprintf(stderr, "sandbox: denied %s '%s'\n", op, path ? path : "(null)");
	}
	errno = EACCES;
	return -1;
}

/**
 * A write whose parent dirs are missing reports ENOENT only when the nearest
 * existing ancestor is inside the grant — git's create-leading-dirs recovery
 * keys off ENOENT, and it must never fire for a tree the policy denies.
 */
static int missing_ancestor(const char *abs) {
	char buf[PATH_MAX];
	snprintf(buf, sizeof buf, "%s", abs);
	char *slash;
	while ((slash = strrchr(buf, '/')) != NULL) {
		if (slash == buf) buf[1] = '\0'; else *slash = '\0';
		char real[PATH_MAX];
		if (realpath(buf, real) == NULL) {
			if (getenv("PI_GATE_DEBUG")) fprintf(stderr, "sandbox: walk %s -> %s\n", buf, strerror(errno));
			if (errno == ENOENT) continue;   /* keep walking up */
			errno = ENOENT; return 0;        /* unreadable ancestor: report fs state */
		}
		if (getenv("PI_GATE_DEBUG")) fprintf(stderr, "sandbox: walk ancestor '%s' allowed=%d\n", real, is_allowed(real));
		if (is_allowed(real)) { errno = ENOENT; return 0; }
		return deny_op("outside-grant", real);
	}
	errno = ENOENT;
	return 0;
}

static int decide_path(const char *path, int dirfd, int follow) {
	pthread_once(&g_once, load_policy);
	if (!path || !*path) return deny_op("null", path);
	char joined[PATH_MAX];
	const char *abs = path;
	if (path[0] != '/') {
		char base[PATH_MAX];
		if (dirfd == AT_FDCWD || dirfd < 0) {
			if (!getcwd(base, sizeof base)) return deny_op("getcwd", path);
		} else {
			char fdlink[64];
			snprintf(fdlink, sizeof fdlink, "/proc/self/fd/%d", dirfd);
			ssize_t n = readlink(fdlink, base, sizeof base - 1);
			if (n <= 0) return deny_op("fd-resolve", path);
			base[n] = '\0';
		}
		if (snprintf(joined, sizeof joined, "%s/%s", base, path) >= (int)sizeof joined) return deny_op("too-long", path);
		abs = joined;
	}
	/* Trailing slashes are legal POSIX (git mkdir()s "hooks/") but break the
	 * parent cut in resolve_parent — strip them, keeping only "/" itself. */
	char clean[PATH_MAX];
	size_t len = strlen(abs);
	while (len > 1 && abs[len - 1] == '/') len--;
	if (len != strlen(abs) || len == 0) {
		if (len >= sizeof clean) return deny_op("too-long", abs);
		memcpy(clean, abs, len);
		clean[len] = '\0';
		if (len == 0) { clean[0] = '/'; clean[1] = '\0'; }
		abs = clean;
	}
	char real[PATH_MAX];
	if (follow) {
		if (realpath(abs, real) == NULL) {
			if (errno != ENOENT) return deny_op("resolve", abs);
			/* final component missing: judge the parent directory */
			if (resolve_parent(abs, real, sizeof real) != 0) {
				if (errno == ENOENT) return missing_ancestor(abs); /* fs state or policy? */
				return deny_op("resolve", abs);
			}
		}
	} else {
		struct stat st;
		if (lstat(abs, &st) == 0 && S_ISLNK(st.st_mode)) {
			if (resolve_parent(abs, real, sizeof real) != 0) {
				if (errno == ENOENT) return missing_ancestor(abs);
				return deny_op("resolve-link", abs);
			}
		} else if (realpath(abs, real) == NULL) {
			if (errno != ENOENT) return deny_op("resolve", abs);
			if (resolve_parent(abs, real, sizeof real) != 0) {
				if (errno == ENOENT) return missing_ancestor(abs);
				return deny_op("resolve", abs);
			}
		}
	}
	if (!is_allowed(real)) return deny_op("outside-grant", real);
	return 1;
}

static int decide(const char *path, int dirfd) { return decide_path(path, dirfd, 1); }
static int decide_nofollow(const char *path, int dirfd) { return decide_path(path, dirfd, 0); }

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
	if (write_flags(flags) && decide(path, AT_FDCWD) != 1) return -1;
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
	if (write_flags(flags) && decide(path, dirfd) != 1) return -1;
	if (flags & O_CREAT) return real_openat(dirfd, path, flags, mode);
	return real_openat(dirfd, path, flags);
}

REAL(creat);
int creat(const char *path, mode_t mode) {
	LOAD(creat) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_creat(path, mode);
}

/* ── stdio ── */
static int write_mode(const char *mode) { return mode && strpbrk(mode, "wa+"); }

REAL(fopen);
FILE *fopen(const char *path, const char *mode) {
	LOAD(fopen) { errno = EACCES; return NULL; }
	if (write_mode(mode) && decide(path, AT_FDCWD) != 1) return NULL;
	return real_fopen(path, mode);
}

REAL(freopen);
FILE *freopen(const char *path, const char *mode, FILE *stream) {
	LOAD(freopen) { errno = EACCES; return NULL; }
	if (write_mode(mode) && decide(path, AT_FDCWD) != 1) return NULL;
	return real_freopen(path, mode, stream);
}

/* ── delete / move ── */
REAL(unlink);
int unlink(const char *path) {
	LOAD(unlink) DENY();
	if (decide_nofollow(path, AT_FDCWD) != 1) return -1;
	return real_unlink(path);
}

REAL(unlinkat);
int unlinkat(int dirfd, const char *path, int flags) {
	LOAD(unlinkat) DENY();
	if (decide_nofollow(path, dirfd) != 1) return -1;
	return real_unlinkat(dirfd, path, flags);
}

REAL(remove);
int remove(const char *path) {
	LOAD(remove) { errno = EACCES; return -1; }
	if (decide_nofollow(path, AT_FDCWD) != 1) return -1;
	return real_remove(path);
}

REAL(rename);
int rename(const char *old, const char *new) {
	LOAD(rename) DENY();
	if (decide_nofollow(old, AT_FDCWD) != 1 || decide_nofollow(new, AT_FDCWD) != 1) return -1;
	return real_rename(old, new);
}

REAL(renameat);
int renameat(int oldfd, const char *old, int newfd, const char *new) {
	LOAD(renameat) DENY();
	if (decide_nofollow(old, oldfd) != 1 || decide_nofollow(new, newfd) != 1) return -1;
	return real_renameat(oldfd, old, newfd, new);
}

#ifdef RENAME_EXCHANGE
REAL(renameat2);
int renameat2(int oldfd, const char *old, int newfd, const char *new, int flags) {
	LOAD(renameat2) DENY();
	if (decide_nofollow(old, oldfd) != 1 || decide_nofollow(new, newfd) != 1) return -1;
	return real_renameat2(oldfd, old, newfd, new, flags);
}
#endif

/* ── make ── */
REAL(mkdir);
int mkdir(const char *path, mode_t mode) {
	LOAD(mkdir) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_mkdir(path, mode);
}

REAL(mkdirat);
int mkdirat(int dirfd, const char *path, mode_t mode) {
	LOAD(mkdirat) DENY();
	if (decide(path, dirfd) != 1) return -1;
	return real_mkdirat(dirfd, path, mode);
}

REAL(rmdir);
int rmdir(const char *path) {
	LOAD(rmdir) DENY();
	if (decide_nofollow(path, AT_FDCWD) != 1) return -1;
	return real_rmdir(path);
}

REAL(link);
int link(const char *old, const char *new) {
	LOAD(link) DENY();
	if (decide(old, AT_FDCWD) != 1 || decide(new, AT_FDCWD) != 1) return -1;
	return real_link(old, new);
}

REAL(linkat);
int linkat(int oldfd, const char *old, int newfd, const char *new, int flags) {
	LOAD(linkat) DENY();
	if (decide(old, oldfd) != 1 || decide(new, newfd) != 1) return -1;
	return real_linkat(oldfd, old, newfd, new, flags);
}

REAL(symlink);
int symlink(const char *target, const char *linkpath) {
	LOAD(symlink) DENY();
	/* The target is interpreted at use time; only the link location writes. */
	if (decide(linkpath, AT_FDCWD) != 1) return -1;
	return real_symlink(target, linkpath);
}

REAL(symlinkat);
int symlinkat(const char *target, int newfd, const char *linkpath) {
	LOAD(symlinkat) DENY();
	if (decide(linkpath, newfd) != 1) return -1;
	return real_symlinkat(target, newfd, linkpath);
}

REAL(mkfifo);
int mkfifo(const char *path, mode_t mode) {
	LOAD(mkfifo) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_mkfifo(path, mode);
}

REAL(mkfifoat);
int mkfifoat(int dirfd, const char *path, mode_t mode) {
	LOAD(mkfifoat) DENY();
	if (decide(path, dirfd) != 1) return -1;
	return real_mkfifoat(dirfd, path, mode);
}

REAL(mknod);
int mknod(const char *path, mode_t mode, dev_t dev) {
	LOAD(mknod) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_mknod(path, mode, dev);
}

REAL(mknodat);
int mknodat(int dirfd, const char *path, mode_t mode, dev_t dev) {
	LOAD(mknodat) DENY();
	if (decide(path, dirfd) != 1) return -1;
	return real_mknodat(dirfd, path, mode, dev);
}

REAL(mkstemp);
int mkstemp(char *template) {
	LOAD(mkstemp) DENY();
	if (decide(template, AT_FDCWD) != 1) return -1;
	return real_mkstemp(template);
}

REAL(mkstemps);
int mkstemps(char *template, int suffixlen) {
	LOAD(mkstemps) DENY();
	if (decide(template, AT_FDCWD) != 1) return -1;
	return real_mkstemps(template, suffixlen);
}

/* ── metadata ── */
REAL(truncate);
int truncate(const char *path, off_t length) {
	LOAD(truncate) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_truncate(path, length);
}

REAL(chmod);
int chmod(const char *path, mode_t mode) {
	LOAD(chmod) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_chmod(path, mode);
}

REAL(fchmodat);
int fchmodat(int dirfd, const char *path, mode_t mode, int flags) {
	LOAD(fchmodat) DENY();
	if (decide(path, dirfd) != 1) return -1;
	return real_fchmodat(dirfd, path, mode, flags);
}

REAL(chown);
int chown(const char *path, uid_t owner, gid_t group) {
	LOAD(chown) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_chown(path, owner, group);
}

REAL(lchown);
int lchown(const char *path, uid_t owner, gid_t group) {
	LOAD(lchown) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_lchown(path, owner, group);
}

REAL(fchownat);
int fchownat(int dirfd, const char *path, uid_t owner, gid_t group, int flags) {
	LOAD(fchownat) DENY();
	if (decide(path, dirfd) != 1) return -1;
	return real_fchownat(dirfd, path, owner, group, flags);
}

#include <sys/time.h>

REAL(utimensat);
int utimensat(int dirfd, const char *path, const struct timespec times[2], int flags) {
	LOAD(utimensat) DENY();
	if (path && decide(path, dirfd) != 1) return -1;
	return real_utimensat(dirfd, path, times, flags);
}

REAL(utimes);
int utimes(const char *path, const struct timeval times[2]) {
	LOAD(utimes) DENY();
	if (decide(path, AT_FDCWD) != 1) return -1;
	return real_utimes(path, times);
}
/* lutimes: absent from bionic; utimensat(AT_SYMLINK_NOFOLLOW) covers the case. */

/* ── probes: keep `test -w` honest outside the grant ── */
REAL(faccessat);
int faccessat(int dirfd, const char *path, int amode, int flags) {
	LOAD(faccessat) DENY();
	if ((amode & W_OK) && decide(path, dirfd) != 1) return -1;
	return real_faccessat(dirfd, path, amode, flags);
}

/* ── libc syscall(): the route around every symbol hook ──
 *
 * A program can reach the kernel without resolving openat/unlinkat through
 * the PLT by calling libc's syscall() dispatcher directly (bypass demo:
 * syscall(SYS_openat, ...) wrote through an earlier build). Interpose it and
 * run the write-family numbers through the same path decision. All numbers
 * come from <sys/syscall.h> — hand-typed ones would misfile innocent calls.
 * Remaining bypass: a program that emits its own svc instructions — that one
 * needs the kernel to enforce, and this kernel offers nothing.
 */
REAL(syscall);
long syscall(long number, ...) {
	LOAD(syscall) { errno = ENOSYS; return -1; }
	long args[5];
	va_list ap;
	va_start(ap, number);
	for (int i = 0; i < 5; i++) args[i] = va_arg(ap, long);
	va_end(ap);

	const char *p1 = NULL, *p2 = NULL;
	int dirfd1 = AT_FDCWD, dirfd2 = AT_FDCWD;
	switch (number) {
		#ifdef SYS_openat
		case SYS_openat:        p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_openat2
		case SYS_openat2:       p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_unlinkat
		case SYS_unlinkat:      p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_mkdirat
		case SYS_mkdirat:       p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_fchmodat
		case SYS_fchmodat:      p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_fchownat
		case SYS_fchownat:      p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_faccessat
		case SYS_faccessat:     p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_mknodat
		case SYS_mknodat:       p1 = (char *)args[1]; dirfd1 = (int)args[0]; break;
		#endif
		#ifdef SYS_truncate
		case SYS_truncate:      p1 = (char *)args[0]; break;
		#endif
		#ifdef SYS_renameat
		case SYS_renameat:      p1 = (char *)args[1]; dirfd1 = (int)args[0];
					p2 = (char *)args[3]; dirfd2 = (int)args[2]; break;
		#endif
		#ifdef SYS_renameat2
		case SYS_renameat2:     p1 = (char *)args[1]; dirfd1 = (int)args[0];
					p2 = (char *)args[3]; dirfd2 = (int)args[2]; break;
		#endif
		#ifdef SYS_linkat
		case SYS_linkat:        p1 = (char *)args[1]; dirfd1 = (int)args[0];
					p2 = (char *)args[3]; dirfd2 = (int)args[2]; break;
		#endif
		#ifdef SYS_symlinkat
		case SYS_symlinkat:     p2 = (char *)args[2]; dirfd2 = (int)args[1]; break;
		#endif
		default: goto run;
	}
	pthread_once(&g_once, load_policy);
	if (p1 && decide_nofollow(p1, dirfd1) != 1) return -1;
	if (p2 && decide_nofollow(p2, dirfd2) != 1) return -1;
run:
	return real_syscall(number, args[0], args[1], args[2], args[3], args[4]);
}

#endif /* PI_GATE_LIB */
