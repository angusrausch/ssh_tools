# SSH Helper
Simple script to automate some SSH tools. Will add onto it if I find something else to automate. 


### Copy SSH public keys
Automatically transfer ssh keys to all hosts within `config.d` directory. 
Use `-k`/`--key` with the key file you want to transfer.
Example usage 
```bash
python3 ssh_helper.py -k ./id_rsa
```
Has optional boolean argument of `-s`/`--sshpass` to use sshpass to automatically send a password if prompted from host.<br><small>Requires sshpass to be install. Not available for windows.<br>Will use a common password for all hosts.</small>
Does not send keys to any hosts in sub directories of the specified config directory. 
Has numerous verbose returns for a key being sent. Will timeout after 5 seconds to manage offline hosts.

### Send Hosts to bastion hosts
Transfer `config.d` directory to all bastion hosts. 
Use `-b`/`--bastion` as argument to activate this option.
Will transfer to all hosts with `bastion` in Host name<br><small>Not hostname in config file but Host</small>.

### Create proxy hosts
Creates proxy hosts to ssh into when outside network using `bastion` host. These will all be within a `proxy/` folder and any contents of a previous folder `proxy/` folder will be removed. Will setup config with `ProxyPass bastion` for each individual host. 
TBD Make a proxy for each bastion for redundancy.