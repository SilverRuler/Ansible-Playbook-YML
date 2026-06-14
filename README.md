#처음에 hosts.ini 접속할 대상에 먼저 ssh 접속해서 핑거프린트 뚫어놔야함
# Ansible-Playbook-YML
Ansible Playbook Collection

```
앤서블 설치
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository --yes --update ppa:ansible/ansible
sudo apt install ansible -y

실행
ansible-playbook -i hosts.ini openvpn_setup.yml
이거 하는 도중에 최신 openvpn들이 자꾸 경로를 바꿔서 sameple-config-files 폴더에 내용이 없다하는데
첨부파일 압축해제

ansible-playbook -i hosts.ini openvpn_client.yml

ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i hosts.ini openvpn_setup.yml


산출물은 
root@aial-craft:~/client-configs/files# ls
```

```
대역대 바꾸기는 다 설치하고
vi /etc/openvpn/server.conf
에서 10.8.0.을 10.8.1. 로
```

``` OCI꺼 접속하는 순간 GCP 라우팅 우선순위 터짐
# 1. 기존 설정 파일 백업
sudo cp /etc/openvpn/client/sr-oci.conf /etc/openvpn/client/sr-oci.conf.bak

# 2. 서버가 푸시하는 라우팅 정책 무시 옵션 추가
echo "route-nopull" | sudo tee -a /etc/openvpn/client/sr-oci.conf

# 3. OCI VPN 서버가 사용하는 가상 IP 대역(예: 10.8.0.0/24)에 대해서만 VPN을 타도록 명시적 라우팅 추가
# (아래 IP와 서브넷 마스크는 OCI OpenVPN 서버의 실제 가상 네트워크 대역에 맞게 수정하여 실행하십시오.)
echo "route 10.8.0.0 255.255.255.0" | sudo tee -a /etc/openvpn/client/sr-oci.conf

# 4. OpenVPN 클라이언트 서비스 재시작
sudo systemctl restart openvpn-client@sr-oci

# 5. 상태 확인
sudo systemctl status openvpn-client@sr-oci
```
