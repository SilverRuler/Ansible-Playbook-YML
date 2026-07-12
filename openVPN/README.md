최신버전의 openvpn에서 샘플코드의 경로가 다르다
```
scp client.conf root@oci2.silverruler.xyz:/usr/share/doc/openvpn/examples/sample-config-files
scp server.conf root@oci2.silverruler.xyz:/usr/share/doc/openvpn/examples/sample-config-files
```

```
#처음에 hosts.ini 접속할 대상에 먼저 ssh 접속해서 핑거프린트 뚫어놔야함
# Ansible-Playbook-YML
Ansible Playbook Collection


앤서블 설치
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository --yes --update ppa:ansible/ansible
sudo apt install ansible -y

실행
ansible-playbook -i hosts.ini openvpn_client.yml

ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i hosts.ini openvpn_setup.yml


산출물은
root@aial-craft:~/client-configs/files# ls

root@ever-chain:~/ansible#
```
