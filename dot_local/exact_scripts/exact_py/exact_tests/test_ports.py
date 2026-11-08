import unittest
from unittest import mock

import _loader

ports = _loader.load("ports")

SAMPLE = """State  Recv-Q Send-Q               Local Address:Port  Peer Address:PortProcess
LISTEN 0      4096                    127.0.0.54:53         0.0.0.0:*
LISTEN 0      4096                       0.0.0.0:5355       0.0.0.0:*   users:(("systemd-resolve",pid=900,fd=17))
LISTEN 0      4096                 127.0.0.53%lo:53         0.0.0.0:*
LISTEN 0      128                        0.0.0.0:22         0.0.0.0:*   users:(("sshd",pid=1234,fd=3))
LISTEN 0      511                      127.0.0.1:8799       0.0.0.0:*
LISTEN 0      4096                 [::]:22                     [::]:*      users:(("sshd",pid=1234,fd=4))
LISTEN 0      4096                      [::1]:9090          [::]:*
LISTEN 0      4096                    100.64.0.1:443        0.0.0.0:*   users:(("tailscale",pid=777,fd=9))
LISTEN 0      4096                    192.168.1.10:8080     0.0.0.0:*
"""


class TestParseSs(unittest.TestCase):
    def test_skips_header_and_blank_lines(self):
        rows = ports.parse_ss(SAMPLE)
        self.assertEqual(len(rows), 9)

    def test_row_fields(self):
        rows = ports.parse_ss(SAMPLE)
        sshd = next(r for r in rows if r["port"] == 22 and r["addr"] == "0.0.0.0")
        self.assertEqual(
            (sshd["proto"], sshd["addr"], sshd["port"], sshd["process"]),
            ("LISTEN", "0.0.0.0", 22, "sshd"),
        )

    def test_ipv6_bracket_addr(self):
        rows = ports.parse_ss(SAMPLE)
        r = next(r for r in rows if r["port"] == 9090)
        self.assertEqual(r["addr"], "::1")

    def test_zone_suffix_stripped(self):
        rows = ports.parse_ss(SAMPLE)
        addrs = {r["addr"] for r in rows if r["port"] == 53}
        self.assertEqual(addrs, {"127.0.0.54", "127.0.0.53"})  # %lo stripped

    def test_no_process_column_is_empty(self):
        rows = ports.parse_ss(SAMPLE)
        r = next(r for r in rows if r["port"] == 8799)
        self.assertEqual(r["process"], "")

    def test_pidless_process_line(self):
        # users:(("foo")) without pid — still extract the name.
        rows = ports.parse_ss('LISTEN 0 128 0.0.0.0:99 0.0.0.0:* users:(("foo"))')
        self.assertEqual(rows[0]["process"], "foo")


class TestClassify(unittest.TestCase):
    def test_wildcards_exposed(self):
        self.assertEqual(ports.classify("0.0.0.0"), "exposed")
        self.assertEqual(ports.classify("::"), "exposed")

    def test_loopback_local(self):
        self.assertEqual(ports.classify("127.0.0.1"), "local")
        self.assertEqual(ports.classify("127.0.0.53"), "local")
        self.assertEqual(ports.classify("::1"), "local")

    def test_specific_addr_bound(self):
        self.assertEqual(ports.classify("100.64.0.1"), "bound")
        self.assertEqual(ports.classify("192.168.1.10"), "bound")
        self.assertEqual(ports.classify("fe80::1"), "bound")


class TestMain(unittest.TestCase):
    def run_main(self, argv):
        out = []
        with mock.patch.object(ports, "subprocess") as sub, mock.patch(
            "builtins.input"
        ):
            sub.run.return_value.stdout = SAMPLE
            sub.run.return_value.returncode = 0
            with mock.patch("sys.stdout") as so:
                so.write = out.append
                so.isatty.return_value = False
                rc = ports.main(argv)
        return rc, "".join(out)

    def test_all_listeners_sorted_by_port(self):
        rc, out = self.run_main([])
        self.assertEqual(rc, 0)
        ports_listed = [int(line.split()[0]) for line in out.splitlines() if line.strip()]
        self.assertEqual(ports_listed, sorted(ports_listed))
        self.assertEqual(len(ports_listed), 9)

    def test_exposed_only_flag(self):
        rc, out = self.run_main(["-e"])
        listed = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(listed), 3)  # 0.0.0.0:5355, 0.0.0.0:22, [::]:22


if __name__ == "__main__":
    unittest.main()
