/*
 * sandbox gate (Windows): low-integrity confinement for a command tree.
 *
 * Windows derives a new process's integrity level from the minimum of the
 * calling user's level and the image file's level. This binary is marked Low
 * integrity (icacls /setintegritylevel L), so executing it yields a Low
 * process, and every process it spawns inherits that token.
 *
 * Mandatory Integrity Control then denies writes upward: a Low process cannot
 * write to a Medium object even when the DACL grants write access. Making a
 * tree writable therefore means labelling it Low with inheritance, which the
 * extension does before launching the gate.
 *
 * Usage — deliberately identical to the Linux gate so the interceptor emits
 * one argument form on both platforms:
 *
 *   gate --ws <workspace-abs> [--allow <abs> ...] [--tmp <abs>] -- <command argv...>
 *
 * --ws and --allow are accepted for parity but not otherwise used: on Windows
 * the writable set is expressed by integrity labels, not by a ruleset. They
 * are still required, so a malformed invocation fails loudly rather than
 * running unconfined.
 *
 * Fails closed: if the gate is not running at Low integrity, nothing runs.
 */

#define _WIN32_WINNT 0x0600
#include <windows.h>
#include <process.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

#define EXIT_NOT_CONFINED 125
#define EXIT_BAD_ARGS 126

/*
 * Is the current process token at Low integrity or below?
 * Returns 1 yes, 0 no, -1 if the level could not be determined.
 * NtQueryInformationToken would be the direct call; this uses the documented
 * Win32 spelling instead so it needs no ntdll import library.
 */
static int own_integrity_is_low(void) {
	HANDLE token = NULL;
	TOKEN_MANDATORY_LABEL *label = NULL;
	DWORD size = 0;
	int result = -1;

	if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) return -1;

	GetTokenInformation(token, TokenIntegrityLevel, NULL, 0, &size);
	if (size == 0) goto done;

	label = (TOKEN_MANDATORY_LABEL *)malloc(size);
	if (!label) goto done;

	if (!GetTokenInformation(token, TokenIntegrityLevel, label, size, &size)) goto done;

	UCHAR sub_authority_count = *GetSidSubAuthorityCount(label->Label.Sid);
	if (sub_authority_count == 0) goto done;
	DWORD rid = *GetSidSubAuthority(label->Label.Sid, (DWORD)(sub_authority_count - 1));
	result = (rid <= SECURITY_MANDATORY_LOW_RID) ? 1 : 0;

done:
	free(label);
	CloseHandle(token);
	return result;
}

/* Point the child's scratch at a Low-labelled directory. The child inherits
 * this process's environment block, so mutating ours is enough. */
static int set_scratch(const wchar_t *dir) {
	if (!dir) return 1;
	return SetEnvironmentVariableW(L"TMP", dir)
	    && SetEnvironmentVariableW(L"TEMP", dir)
	    && SetEnvironmentVariableW(L"TMPDIR", dir);
}

int main(void) {
	int argc = 0;
	wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
	if (!argv) {
		fprintf(stderr, "sandbox: cannot parse command line\n");
		return EXIT_BAD_ARGS;
	}

	/* Probe: is the low-integrity drop actually in effect on this machine? */
	if (argc == 2 && wcscmp(argv[1], L"--probe") == 0) {
		int low = own_integrity_is_low();
		if (low == 1) return 0;
		if (low == 0)
			fprintf(stderr, "sandbox: gate is not at Low integrity — the "
			                "image label was not applied\n");
		else
			fprintf(stderr, "sandbox: cannot read this process's integrity level\n");
		return EXIT_NOT_CONFINED;
	}

	const wchar_t *ws = NULL;
	const wchar_t *tmp = NULL;
	int i = 1;
	while (i < argc) {
		if (wcscmp(argv[i], L"--ws") == 0 && i + 1 < argc) {
			ws = argv[i + 1];
			i += 2;
		} else if (wcscmp(argv[i], L"--allow") == 0 && i + 1 < argc) {
			i += 2;
		} else if (wcscmp(argv[i], L"--tmp") == 0 && i + 1 < argc) {
			tmp = argv[i + 1];
			i += 2;
		} else if (wcscmp(argv[i], L"--") == 0) {
			i++;
			break;
		} else {
			fprintf(stderr, "sandbox: unexpected argument\n");
			return EXIT_BAD_ARGS;
		}
	}

	if (!ws) {
		fprintf(stderr, "sandbox: missing --ws\n");
		return EXIT_BAD_ARGS;
	}
	if (i >= argc) {
		fprintf(stderr, "sandbox: no command to run\n");
		return EXIT_BAD_ARGS;
	}

	if (own_integrity_is_low() != 1) {
		fprintf(stderr, "sandbox: refusing to run — not at Low integrity\n");
		return EXIT_NOT_CONFINED;
	}

	if (!set_scratch(tmp)) {
		fprintf(stderr, "sandbox: cannot point TMP/TEMP at the scratch directory\n");
		return EXIT_NOT_CONFINED;
	}

	/* The child inherits this Low token, so the whole tree stays confined. */
	intptr_t status = _wspawnvp(_P_WAIT, argv[i], (const wchar_t *const *)&argv[i]);
	if (status == -1) {
		fprintf(stderr, "sandbox: cannot run the requested command\n");
		return 127;
	}
	return (int)status;
}
