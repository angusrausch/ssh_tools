import os
import re
import shutil
from argparse import ArgumentParser
import subprocess
import sys
from getpass import getpass

def main(args):
    config_path = os.path.expanduser("~/.ssh/config.d")

    if args.proxy:
        create_proxies(config_path)
    if args.bastion:
        send_hosts(config_path)
    if args.key:
        add_keys(config_path, args)

def add_keys(config_path, args, timeout = 5):
    key_path = os.path.abspath(args.key)
    sshpass = args.sshpass
    if sshpass:
        check_sshpass = subprocess.run(["which", "sshpass"], capture_output=True, text=True)
        check_sshpass_string = str(check_sshpass)
        if check_sshpass_string == "" or check_sshpass_string == "sshpass not found" or check_sshpass.returncode != 0:
            print("sshpass not found on system. Please install it or remove -s argument")
            sys.exit()
    hosts = get_hosts(config_path)
    print(f"Sending keys to Hosts. This may take a while, current timeout is set to {timeout} Seconds per Host")
    print("If you would like to skip a host use \"ctrl c\"")
    print("=========================================")
    send_keys_to_hosts(hosts, key_path, sshpass, timeout)

def send_keys_to_hosts(hosts, key_path, sshpass, timeout):
    password = get_sshpass_password() if sshpass else None
    for host in hosts:
        host_short = re.search(r"(?i)Host\s+(\S+)", host)
        host_short = host_short.group(1) if host_short else ''
        print(f"Sending key to Host: {host_short}")
        copy_id_command = ["ssh-copy-id", "-i", key_path, host_short]

        if sshpass:
            copy_id_command = ["sshpass", "-p", password] + copy_id_command
        try:
            result = subprocess.run(copy_id_command, timeout=timeout, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            print("Failed to upload Key: Timeout")
        except KeyboardInterrupt:
            print("\nHost skipped - User request")
        else:
            result_string = str(result)
            if "WARNING: All keys were skipped because they already exist on the remote system." in result_string:
                print("Key already on host")
            elif "Permission denied (publickey)." in result_string:
                print("Failed to upload Key: Permission Denied - Requires publickey")
            elif result.returncode != 0:
                if "Permission denied, please try again." in result_string:
                    print("Failed to upload Key: Incorrect password inputted for sshpass")
                else: 
                    print("Failed to upload key: Unknown Error")
                    print(result_string)
            else:
                print(f"Key uploaded to {host_short}")
        print("-----------------------------------------")
    cleanup_temp_files()

def cleanup_temp_files():
    print("Cleaning up")
    directories = [os.curdir, os.path.expanduser("~") + "/.ssh"]
    for directory in directories:
        for temp_file in os.listdir(directory):
            if temp_file.startswith('ssh-copy-id.'):
                try:
                    shutil.rmtree(os.path.join(directory, temp_file))
                except Exception as e:
                    print(f"Failed to clean up {temp_file}: {str(e)}")

def get_sshpass_password():
    print("Please input common password for use with sshpass")
    try:
        return getpass()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit()

def get_hosts(config_path):
    hosts = []
    all_hosts_files = os.listdir(config_path)
    for host_file in all_hosts_files:
        if os.path.isfile(os.path.join(config_path, host_file)):
            with open(os.path.join(config_path, host_file), "r") as file:
                file_contents = file.read()
                pattern = r'(?i)Host [^\n]+(?:\n\s+[^\n]+)+'
                found_hosts = re.findall(pattern, file_contents)
                for host in found_hosts:
                    hosts.append(host)
    return hosts

def send_hosts(config_path):
    bastions = get_bastions(config_path)
    for bastion in bastions:
        scp_command = ["scp", "-r", config_path, f"{bastion}:.ssh"]
        subprocess_output = subprocess.run(scp_command, timeout=10, capture_output=True, text=True)
        if subprocess_output.returncode != 0:
            print("Error occured during transfer")

def get_bastions(config_path):
    all_hosts = get_hosts(config_path)
    bastions = []
    for host in all_hosts:
        host_names = re.search(r"(?i)Host\s+([^\n]+)", host)
        host_names = host_names.group(1) if host_names else ''
        if "bastion" in host_names:
            host_short = host_names.split(" ")[0]
            bastions.append(host_short)
    return bastions

def create_proxies(path):
    proxy_folder = "proxy"
    ignore_list = [proxy_folder, f"{proxy_folder}-copy", '.DS_Store']
    
    all_hosts_files = os.listdir(path)
    
    set_proxy_folder(path, proxy_folder)

    ignore_files(ignore_list, all_hosts_files)
    
    try:
        make_proxy_files(path, proxy_folder, all_hosts_files)
    except Exception as e:
        revert_proxy(path, proxy_folder)
        print(f"Error has occured: Reverting back to previous version")
        print(e)
    else:
        remove_proxy_copy(path, proxy_folder)

def set_proxy_folder(path, proxy_folder):
    proxy_copy_dir = f"{path}/{proxy_folder}-copy"
    proxy_dir = f"{path}/{proxy_folder}"
    if os.path.exists(proxy_copy_dir):
        shutil.rmtree(proxy_copy_dir)
    if os.path.exists(proxy_dir):
        shutil.move(proxy_dir, proxy_copy_dir)
    os.mkdir(f"{path}/{proxy_folder}")

def ignore_files(ignore_list, all_hosts_files):
    for ignore_file in ignore_list:
            if ignore_file in all_hosts_files:
                all_hosts_files.remove(ignore_file)

def modify_host_line(match, bastion):
    host_keyword = match.group(1)
    words = match.group(2).split()
    modified_words = " ".join(f"{bastion}-{word}" for word in words)
    proxy_jump_line = f"    proxyJump {bastion}"    
    return f"{host_keyword} {modified_words}\n{proxy_jump_line}"

def make_proxy_files(config_path, proxy_folder, all_hosts_files):
    bastions = get_bastions(config_path)
    for bastion in bastions:
        bastion_proxy_path = f"{config_path}/{proxy_folder}/{bastion}"
        os.mkdir(bastion_proxy_path)
        for host_file in all_hosts_files:
            file = open(f"{config_path}/{host_file}", "r")
            file_contents = file.read()

            new_file_contents = re.sub(
                r"(?i)^(Host) ([^\n]+)",
                lambda match: modify_host_line(match, bastion),
                file_contents,
                flags=re.MULTILINE
            )

            proxy_file = open(f"{bastion_proxy_path}/{host_file}", "x")
            proxy_file.write(new_file_contents)
            proxy_file.close()
    create_config_file(bastions, proxy_folder)

def create_config_file(bastions, proxy_folder):
    file = open(os.path.expanduser("~/.ssh/config"), "w")
    relative_config_dir = "config.d/"
    file_contents = f"include {relative_config_dir}* "
    relative_proxy_dir = f"{relative_config_dir}{proxy_folder}"
    for bastion in bastions:
        relative_bastion_dir = f"{relative_proxy_dir}/{bastion}/* "
        file_contents += relative_bastion_dir
    file.write(file_contents)
    file.close()


def revert_proxy(path, proxy_folder):
    proxy_copy_dir = f"{path}/{proxy_folder}-copy"
    proxy_dir = f"{path}/{proxy_folder}"
    if os.path.exists(proxy_copy_dir):
        if os.path.exists(proxy_folder):
            shutil.rmtree(proxy_folder)
        shutil.move(proxy_copy_dir, proxy_dir)

def remove_proxy_copy(path, proxy_folder):
    proxy_copy_dir = f"{path}/{proxy_folder}-copy"
    shutil.rmtree(proxy_copy_dir)


if __name__ == "__main__":
    parser = ArgumentParser(description="SSH Config helper & send proxy keys")
    parser.add_argument("-p", "--proxy", action="store_true", help="Create proxy based off of configs")
    parser.add_argument("-b", "--bastion", action="store_true", help="Send config to bastions")
    parser.add_argument("-k", "--key", type=str, help="Add key to host authorised keys")
    parser.add_argument("-s", "--sshpass", action="store_true", help="Use sshpass for sending key")
    args = parser.parse_args()
    main(args)