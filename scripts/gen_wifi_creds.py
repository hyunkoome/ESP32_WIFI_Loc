#!/usr/bin/env python3
"""
gen_wifi_creds.py
=================
config.yaml 의 wifi.ssid / wifi.password 를 읽어, 진단 펌웨어가 빌드 시 포함할
C 헤더(wifi_credentials.h)를 생성한다. WiFi "접속" 테스트(report_wifi_connect)가
이 값으로 실제 AP 에 붙어 본다.

step01_build_diag_firmware.sh 가 idf.py build 직전에 호출한다.

특징:
  - PyYAML 이 있으면 사용하고, 없으면 최소 파서로 폴백한다(ESP-IDF python 환경
    에서도 의존성 없이 동작하도록).
  - config.yaml 이 없거나 자격증명이 비어 있으면 빈 값으로 헤더를 생성한다
    → 펌웨어가 접속 테스트를 생략(SKIP)한다.
  - 생성된 헤더는 비밀번호를 포함하므로 .gitignore 처리된다.

사용:
  python3 gen_wifi_creds.py <config.yaml 경로> <출력 헤더 경로>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


def _parse_with_yaml(text: str) -> Optional[Tuple[str, str]]:
    """PyYAML 로 wifi.ssid/password 추출. 실패/미설치면 None."""
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        data = yaml.safe_load(text) or {}
        wifi = data.get("wifi") or {}
        return str(wifi.get("ssid") or ""), str(wifi.get("password") or "")
    except Exception:
        return None


def _parse_minimal(text: str) -> Tuple[str, str]:
    """PyYAML 없이 'wifi:' 블록의 ssid/password 만 뽑는 최소 파서.

    예상 형식:
        wifi:
          ssid: "..."
          password: "..."
    """
    ssid = ""
    password = ""
    in_wifi = False
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 들여쓰기 없는 키 = 최상위 블록. 'wifi:' 진입/이탈 판정.
        if not line[:1].isspace():
            in_wifi = stripped.rstrip(":") == "wifi" and stripped.endswith(":")
            continue
        if not in_wifi:
            continue
        m = re.match(r"(ssid|password)\s*:\s*(.*)$", stripped)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        # 따옴표 제거(있으면).
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        if key == "ssid":
            ssid = val
        else:
            password = val
    return ssid, password


def load_credentials(config_path: Path) -> Tuple[str, str]:
    if not config_path.exists():
        return "", ""
    text = config_path.read_text(encoding="utf-8")
    via_yaml = _parse_with_yaml(text)
    if via_yaml is not None:
        return via_yaml
    return _parse_minimal(text)


def write_header(out_path: Path, ssid: str, password: str) -> None:
    # json.dumps 로 C 문자열 리터럴에 안전하게 이스케이프(", \\, 제어문자).
    ssid_lit = json.dumps(ssid)
    pw_lit = json.dumps(password)
    content = (
        "// 자동 생성됨 (scripts/gen_wifi_creds.py). 직접 수정하지 마세요.\n"
        "// config.yaml 의 wifi.ssid / wifi.password 를 빌드 시 주입.\n"
        "// 비밀번호를 포함하므로 .gitignore 처리됩니다.\n"
        "#pragma once\n"
        f"#define DIAG_WIFI_SSID {ssid_lit}\n"
        f"#define DIAG_WIFI_PASSWORD {pw_lit}\n"
    )
    out_path.write_text(content, encoding="utf-8")


def main(argv) -> int:
    if len(argv) != 3:
        print("사용법: gen_wifi_creds.py <config.yaml> <out.h>", file=sys.stderr)
        return 2
    config_path = Path(argv[1])
    out_path = Path(argv[2])
    ssid, password = load_credentials(config_path)
    write_header(out_path, ssid, password)
    if ssid:
        print(f"[gen_wifi_creds] WiFi 접속 테스트 대상 SSID: {ssid}")
    else:
        print("[gen_wifi_creds] config.yaml 자격증명 없음 — WiFi 접속 테스트는 SKIP 됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
