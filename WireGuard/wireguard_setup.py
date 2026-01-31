import os, subprocess, re, sys

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ 실행 에러: {e.output.decode('utf-8')}")
        return None

def install_dependencies():
    print("📦 필수 패키지 확인 및 설치 중...")
    run_cmd("sudo apt update && sudo apt install -y wireguard qrencode curl iptables ufw")

def get_server_info():
    pub_ip = run_cmd("curl -s ifconfig.me")
    iface_info = run_cmd("ip route get 8.8.8.8")
    eth_iface = re.search(r"dev (\S+)", iface_info).group(1)
    return pub_ip, eth_iface

def setup_server():
    if not os.path.exists("/etc/wireguard/wg0.conf"):
        print("🔧 서버 초기 설정을 시작합니다...")
        pub_ip, eth = get_server_info()
        s_priv = run_cmd("wg genkey")
        s_pub = run_cmd(f"echo {s_priv} | wg pubkey")
        
        # Peer간 통신(P2P) 및 NAT 설정
        conf = f"""[Interface]
Address = 10.0.0.1/24
ListenPort = 51820
PrivateKey = {s_priv}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o {eth} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o {eth} -j MASQUERADE
"""
        with open("/etc/wireguard/wg0.conf", "w") as f:
            f.write(conf)
        
        # 커널 포워딩 및 서비스 활성화
        os.system("echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-wg.conf && sysctl -p /etc/sysctl.d/99-wg.conf")
        run_cmd("wg-quick up wg0")
        run_cmd("systemctl enable wg-quick@wg0")
        
        # 🔥 OS 방화벽(UFW) 포트 허용 추가
        print("🛡️ UFW 방화벽에서 51820/udp 포트를 허용합니다...")
        run_cmd("sudo ufw allow 51820/udp")
        
        print("✅ 서버가 성공적으로 시작되었습니다.")

def create_bulk_peers(count=10):
    pub_ip, _, _ = (get_server_info() + (None,))
    s_pub = run_cmd("wg show wg0 public-key")
    os.makedirs("./configs", exist_ok=True)
    
    with open("/etc/wireguard/wg0.conf", "r") as f:
        conf_content = f.read()
        existing_ips = re.findall(r"10\.0\.0\.(\d+)", conf_content)
        last_ip = max([int(i) for i in existing_ips] + [1])

    print(f"📁 {count}개의 Peer 설정을 생성합니다...")
    for i in range(1, count + 1):
        new_tail = last_ip + i
        new_ip = f"10.0.0.{new_tail}"
        c_priv = run_cmd("wg genkey")
        c_pub = run_cmd(f"echo {c_priv} | wg pubkey")

        # 서버에 실시간 반영
        run_cmd(f"wg set wg0 peer {c_pub} allowed-ips {new_ip}/32")
        
        # 설정 파일 영구 기록
        with open("/etc/wireguard/wg0.conf", "a") as f:
            f.write(f"\n[Peer]\nPublicKey = {c_pub}\nAllowedIPs = {new_ip}/32\n")

        # 클라이언트용 파일 생성
        client_conf = f"""[Interface]
PrivateKey = {c_priv}
Address = {new_ip}/32
DNS = 1.1.1.1

[Peer]
PublicKey = {s_pub}
Endpoint = {pub_ip}:51820
AllowedIPs = 0.0.0.0/0, 10.0.0.0/24
PersistentKeepalive = 25
"""
        with open(f"./configs/user_{new_tail}.conf", "w") as f:
            f.write(client_conf)
            
    print(f"✨ 완료! ./configs 폴더에 파일들이 저장되었습니다.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("❌ 반드시 sudo python3로 실행하세요.")
        sys.exit(1)
    install_dependencies()
    setup_server()
    create_bulk_peers(10)
