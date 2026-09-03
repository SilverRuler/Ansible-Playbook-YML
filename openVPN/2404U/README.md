# OpenVPN Ansible 플레이북 - Ubuntu 24.04 대응 이슈 분석 및 해결 기록

작성일: 2026-07-13  
작성자: Antigravity (AI 페어 프로그래밍)  
대상 OS: Ubuntu 24.04 LTS (Noble Numbat)  
기존 OS: Ubuntu 22.04 LTS (Jammy Jellyfish)

---

## 1. 문제 개요

Ubuntu 22.04 기준으로 정상 동작하던 `openvpn_setup.yml` + `openvpn_client.yml` Ansible 플레이북을
Ubuntu 24.04 대상 서버에 실행했을 때, **마지막 OpenVPN 서비스 시작 단계에서 에러가 발생**했다.

```
TASK [37. OpenVPN 서비스 상태 확인]
fatal: [gcp-test-server]: FAILED!
  msg: "non-zero return code"
  rc: 3
  stdout: |
    Active: activating (auto-restart) (Result: exit-code)
    Process: ExecStart=... (code=exited, status=1/FAILURE)
    Status: "Pre-connection initialization successful"
```

---

## 2. 에러 원인 분석

### 2-1. [결정적 원인] 포트 충돌 (3300/tcp)

플레이북은 OpenVPN 포트를 기본 `1194`에서 `3300/tcp`로 변경하도록 설정되어 있다.
그런데 해당 서버에는 이미 **`3proxy`** 프로세스가 `3300` 포트를 점유하고 있었다.

```
# ss -tulpn | grep 3300
tcp  LISTEN  0  626  0.0.0.0:3300  0.0.0.0:*  users:(("3proxy",pid=8203,fd=5))
```

journalctl 로그를 확인한 결과, OpenVPN 데몬이 tun0 인터페이스 생성까지는 성공했으나
소켓 바인딩 단계에서 실패하며 종료되었다.

```
TCP/UDP: Socket bind failed on local address [AF_INET][undef]:3300: Address already in use (errno=98)
Exiting due to fatal error
```

이 문제는 Ubuntu 버전 자체의 차이가 아니라, **해당 서버에 추가로 설치된 서비스와의 포트 충돌**이었다.
22.04 서버에서는 3proxy가 없었기에 정상 동작했던 것이다.

### 2-2. [컨트롤러 환경 이슈] Ansible 버전과 Python 3.12 비호환

Ubuntu 24.04는 기본 Python 버전이 **Python 3.12**이다.  
Ansible 컨트롤러에 설치된 구버전 Ansible(`2.10.x` 계열)은 Python 3.12 환경을 제어할 때
내부 모듈 경로 문제로 다음 에러를 발생시킨다.

```
ModuleNotFoundError: No module named 'ansible.module_utils.six.moves'
```

Ansible 2.10 시절에는 `six` 라이브러리를 자체 내장(`ansible.module_utils.six`)하고 있었는데,
Python 3.12에서는 이 내부 경로가 정상적으로 해석되지 않는다.

**해결**: `pip3 install --upgrade ansible`로 `ansible-core 2.17.x`로 업그레이드

```bash
pip3 install --upgrade ansible
# 설치된 버전: ansible-10.7.0 / ansible-core-2.17.14
```

### 2-3. [Ubuntu 24.04 / OpenVPN 2.6 주요 변경사항] (경고 수준, 서비스 구동에는 무관)

Ubuntu 24.04에 패키지 설치되는 OpenVPN은 `2.6.x` 계열이다.
2.5 → 2.6으로 올라오면서 아래 항목들이 변경되었다.

| 항목 | 기존 (2.4/2.5) | 변경 (2.6+) |
|---|---|---|
| ta.key 생성 명령 | `openvpn --genkey --secret ta.key` | `openvpn --genkey secret ta.key` |
| cipher 설정 | `cipher AES-256-CBC` 단독 사용 | `data-ciphers` 추가 권장 |
| 토폴로지 | `topology net30` (기본값) | `topology subnet` 권장 (net30 지원 종료 예정) |

이 항목들은 서비스 구동 자체를 막지는 않지만, journalctl에 WARNING/DEPRECATED 로그를 남긴다.

---

## 3. 해결 방법

### Step 1. Ansible 컨트롤러 업그레이드

```bash
pip3 install --upgrade ansible
```

### Step 2. 포트 3300 확보 (3proxy 중지)

```bash
# Ansible로 원격 실행
ansible -i hosts.ini gcp_nodes -m shell -a "systemctl stop 3proxy"
```

### Step 3. openvpn_setup.yml → openvpn@server 재구동

포트가 확보된 상태에서 플레이북을 재실행하면 정상 완료.

```bash
ansible-playbook -i hosts.ini openvpn_setup.yml
ansible-playbook -i hosts.ini openvpn_client.yml
```

### Step 4. 자동시작 등록 확인

플레이북 내 `systemd` 태스크에 `enabled: yes`가 이미 명시되어 있어
재부팅 후 자동 시작이 등록된 상태로 완료된다.

```bash
# 확인 명령
ansible -i hosts.ini gcp_nodes -m shell -a "systemctl is-enabled openvpn@server"
# 출력: enabled

ansible -i hosts.ini gcp_nodes -m shell -a "systemctl is-active openvpn@server"
# 출력: active
```

---

## 4. 24.04 전용 개선 플레이북

위 분석을 바탕으로, Ubuntu 24.04 + OpenVPN 2.6 환경에 최적화된 플레이북을 별도 작성하였다.

- `260713openvpn_setup.yml` : 서버 구축 플레이북
- `260713openvpn_client.yml` : 클라이언트 ovpn 파일 생성 플레이북

### 기존 대비 주요 변경사항

| 항목 | 기존 플레이북 | 개선 플레이북 |
|---|---|---|
| Ansible 최소 요구 버전 | 2.10 | 2.17+ 권장 |
| `ta.key` 생성 | `--genkey --secret` (deprecated) | `--genkey secret` (2.6+ 정식 문법) |
| cipher 설정 | `cipher AES-256-CBC` 단독 | `data-ciphers AES-256-GCM:AES-256-CBC` + `cipher AES-256-CBC` |
| topology | net30 (기본, deprecated 예정) | `topology subnet` 명시 |
| 포트 충돌 대응 | 없음 | pre_tasks에서 3300 포트 선점 프로세스 자동 중지 |
| Python 인터프리터 경고 | 매번 WARNING 출력 | `ansible_python_interpreter: auto` 명시 |

---

## 5. 클라이언트 파일 배포

구축 완료 후 클라이언트 접속에 필요한 파일 2종을 tar로 묶어 컨트롤러 서버 `/root`에 배치하였다.

```bash
# 원격 서버에서 tar 생성
ansible -i hosts.ini gcp_nodes -m shell -a \
  "tar czf /tmp/vpn_client_files.tar.gz \
   -C /root/client-configs/files tongchun.ovpn \
   -C /root/client-configs/keys ta.key"

# 로컬로 fetch
ansible -i hosts.ini gcp_nodes -m fetch -a \
  "src=/tmp/vpn_client_files.tar.gz dest=/root/vpn_client_files.tar.gz flat=yes"
```

배치 위치: `/root/vpn_client_files.tar.gz`  
압축 내용:
```
tongchun.ovpn   ← OpenVPN 클라이언트 설정 파일 (인증서 인라인 포함)
ta.key          ← TLS 인증 키
```

클라이언트에서는 이 두 파일을 같은 디렉토리에 놓고 `tongchun.ovpn`을 OpenVPN 클라이언트에 불러오면 된다.

---

## 6. 환경 정보

| 항목 | 값 |
|---|---|
| 대상 서버 OS | Ubuntu 24.04 LTS (Noble Numbat) |
| OpenVPN 버전 | 2.6.x |
| EasyRSA 버전 | 3.0.4 |
| VPN 포트 | 3300/tcp |
| VPN 서브넷 | 10.8.0.0/24 |
| 클라이언트 이름 | tongchun |
| Ansible 컨트롤러 버전 | ansible-core 2.17.14 |
