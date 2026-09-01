/*
 * sandbox gate: kernel-enforced read-only layer via Landlock (Linux >= 5.13).
 *
 * Runs a command under a Landlock ruleset that allows reads everywhere and
 * writes only inside the workspace plus an explicit allowlist. The ruleset
 * is inherited by the shell and every child process. No root, no container.
 *
 * Usage:
 *   gate --ws <workspace-abs> [--allow <abs-prefix> ...] -- <command argv...>
 *
 * Fails closed: if Landlock is unavailable the command does not run.
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/landlock.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef SYS_landlock_create_ruleset
#define SYS_landlock_create_ruleset 444
#endif
#ifndef SYS_landlock_add_rule
#define SYS_landlock_add_rule 445
#endif
#ifndef SYS_landlock_restrict_self
#define SYS_landlock_restrict_self 446
#endif

#define READ_BITS                                                        \
	(LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_FILE |          \
	 LANDLOCK_ACCESS_FS_READ_DIR)

#define WRITE_BITS                                                       \
	(LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_REMOVE_DIR |      \
	 LANDLOCK_ACCESS_FS_REMOVE_FILE | LANDLOCK_ACCESS_FS_MAKE_CHAR |      \
	 LANDLOCK_ACCESS_FS_MAKE_DIR | LANDLOCK_ACCESS_FS_MAKE_REG |          \
	 LANDLOCK_ACCESS_FS_MAKE_SOCK | LANDLOCK_ACCESS_FS_MAKE_FIFO |        \
	 LANDLOCK_ACCESS_FS_MAKE_BLOCK | LANDLOCK_ACCESS_FS_MAKE_SYM)

static int add_rule(int fd, uint64_t access, const char *path) {
	int dirfd = open(path, O_PATH | O_CLOEXEC);
	if (dirfd < 0) {
		fprintf(stderr, "sandbox: cannot open \"%s\": %s\n", path, strerror(errno));
		return -1;
	}
	struct landlock_path_beneath_attr attr = { .allowed_access = access, .parent_fd = dirfd };
	if (syscall(SYS_landlock_add_rule, fd, LANDLOCK_RULE_PATH_BENEATH, &attr, 0) != 0) {
		fprintf(stderr, "sandbox: add_rule failed for \"%s\": %s\n", path, strerror(errno));
		close(dirfd);
		return -1;
	}
	close(dirfd);
	return 0;
}

int main(int argc, char **argv) {
	/* Probe mode: verify Landlock works, then exit. */
	if (argc == 2 && strcmp(argv[1], "--probe") == 0) {
		int abi = (int)syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
		if (abi < 1) {
			fprintf(stderr, "Landlock unavailable (ABI %d)\n", abi);
			return 125;
		}
		uint64_t handled = READ_BITS;
		struct landlock_ruleset_attr attr = { .handled_access_fs = handled };
		int rfd = (int)syscall(SYS_landlock_create_ruleset, &attr, sizeof attr, 0);
		if (rfd < 0 || add_rule(rfd, READ_BITS, "/") != 0 ||
		    prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0 ||
		    syscall(SYS_landlock_restrict_self, rfd, 0) != 0) {
			fprintf(stderr, "Landlock unavailable: %s\n", strerror(errno));
			return 125;
		}
		return 0;
	}

	const char *ws = NULL;
	const char *allows[64];
	int nallows = 0;
	int i = 1;
	while (i < argc) {
		if (strcmp(argv[i], "--ws") == 0 && i + 1 < argc) {
			ws = argv[++i];
			i++;
		} else if (strcmp(argv[i], "--allow") == 0 && i + 1 < argc) {
			if (nallows < 64) allows[nallows++] = argv[++i];
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

	/* Resolve the workspace to an absolute path. */
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

	/* Landlock ABI version (>= 1 required). */
	int abi = (int)syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
	if (abi < 1) {
		fprintf(stderr, "sandbox: Landlock unavailable (ABI %d): %s — command refused\n",
			abi, abi < 0 ? strerror(-abi) : "unsupported");
		return 125;
	}

	uint64_t handled = READ_BITS | WRITE_BITS;
	if (abi >= 2) handled |= LANDLOCK_ACCESS_FS_TRUNCATE;

	struct landlock_ruleset_attr attr = { .handled_access_fs = handled };
	int rfd = (int)syscall(SYS_landlock_create_ruleset, &attr, sizeof attr, 0);
	if (rfd < 0) {
		perror("sandbox: create_ruleset");
		return 125;
	}

	/* Reads + execute everywhere. */
	if (add_rule(rfd, READ_BITS, "/") != 0) return 125;
	/* Full access under the workspace. */
	if (add_rule(rfd, handled, wsabs) != 0) return 125;
	/* Full access under each allowlist prefix. */
	for (int j = 0; j < nallows; j++) {
		if (add_rule(rfd, handled, allows[j]) != 0) return 125;
	}

	/* Unprivileged callers must set no_new_privs (also blocks setuid
	 * escalation inside the sandbox). */
	if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
		perror("sandbox: prctl(NO_NEW_PRIVS)");
		return 125;
	}

	if (syscall(SYS_landlock_restrict_self, rfd, 0) != 0) {
		perror("sandbox: restrict_self");
		return 125;
	}
	close(rfd);

	execvp(argv[i], &argv[i]);
	perror("sandbox: exec");
	return 127;
}