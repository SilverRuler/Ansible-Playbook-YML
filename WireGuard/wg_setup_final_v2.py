import os, subprocess, re, sys, time

def run_cmd(cmd, ignore_error=False):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            print(f"❌ 명령 실패: {cmd}")
            print(f"📝 에러 내용: {e.output.decode('utf-8')}")
        return None

def get_server_info():
    # 192.168.1.x 대역을 먼저 찾음
    iface_info = run_cmd("ip -4 route show | grep 192.168.1.0/24", True)
    if iface_info and "dev" in iface_info:
        eth_iface = re.search(r"dev (\S+)", iface_info).group(1)
        gw_ip = "192.168.1.1"
    else:
        # 없으면 기본 경로에서 찾음
        default_route = run_cmd("ip -4 route show default | grep -v 'tun' | grep -v 'wg' | head -n 1")
        eth_iface = re.search(r"dev (\S+)", default_route).group(1)
        gw_ip = re.search(r"via (\S+)", default_route).group(1)

    pub_ip = run_cmd("curl -s ifconfig.me")
    return pub_ip, eth_iface, gw_ip

def setup_server():
    if os.path.exists("/etc/wireguard/wg0.conf"):
        return # 이미 있으면 스킵

    print("🔧 서버 초기 설정을 시작합니다...")
    pub_ip, eth, gw = get_server_info()
    s_priv = run_cmd("wg genkey")
    s_pub = run_cmd(f"echo {s_priv} | wg pubkey")

    # PostUp에 ip route flush table 123를 추가하여 기존 경로 찌꺼기를 완전히 제거합니다.
    conf = f"""[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = {s_priv}
PostUp = ip route flush table 123 || true; while ip rule del from 10.0.0.0/24 table 123 2>/dev/null; do :; done; ip rule add from 10.0.0.0/24 table 123; ip route add default via {gw} dev {eth} table 123; iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o {eth} -j MASQUERADE
PostDown = ip rule del from 10.0.0.0/24 table 123; iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o {eth} -j MASQUERADE
"""
    with open("/etc/wireguard/wg0.conf", "w") as f:
        f.write(conf)

    os.system("echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-wg.conf && sysctl -p /etc/sysctl.d/99-wg.conf")

    print(f"🚀 인터페이스 활성화 ({eth}, {gw})...")
    res = run_cmd("wg-quick up wg0")
    if res is None:
        print("🛑 wg-quick 실행에 실패했습니다. 위 에러 메시지를 확인하세요.")
        sys.exit(1)

    run_cmd("systemctl enable wg-quick@wg0", True)
    run_cmd("sudo ufw allow 51820/udp", True)
    print("✅ 서버 인터페이스가 성공적으로 생성되었습니다.")

def create_bulk_peers(count=10):
    # 인터페이스가 실제로 떴는지 확인
    time.sleep(1) # 커널이 인터페이스를 준비할 시간을 잠깐 줌
    s_pub = run_cmd("wg show wg0 public-key")
    if not s_pub:
        print("❌ 에러: wg0 인터페이스를 찾을 수 없습니다. (Handshake/Key 조회 실패)")
        sys.exit(1)

    pub_ip, eth, _ = get_server_info()
    os.makedirs("./configs", exist_ok=True)

    print(f"📁 {count}개의 Peer 설정을 생성합니다...")
    for i in range(1, count + 1):
        new_tail = 1 + i
        new_ip = f"10.0.0.{new_tail}"
        c_priv = run_cmd("wg genkey")
        c_pub = run_cmd(f"echo {c_priv} | wg pubkey")

        run_cmd(f"wg set wg0 peer {c_pub} allowed-ips {new_ip}/32")
        with open("/etc/wireguard/wg0.conf", "a") as f:
            f.write(f"\n[Peer]\nPublicKey = {c_pub}\nAllowedIPs = {new_ip}/32\n")

        client_conf = f"""[Interface]
PrivateKey = {c_priv}
Address = {new_ip}/32
DNS = 1.1.1.1

[Peer]
PublicKey = {s_pub}
Endpoint = {pub_ip}:51820
AllowedIPs = 0.0.0.0/0, 10.0.0.0/24, 192.168.1.0/24
PersistentKeepalive = 25
"""
        with open(f"./configs/user_{new_tail}.conf", "w") as f:
            f.write(client_conf)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("❌ sudo 권한이 필요합니다.")
        sys.exit(1)
    setup_server()
    create_bulk_peers(10)
    print("✨ 모든 작업이 완료되었습니다! ./configs 폴더를 확인하세요.")
