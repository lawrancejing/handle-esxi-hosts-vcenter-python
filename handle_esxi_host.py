from pyVmomi import vim
import time
import subprocess

"""
Retrive ESXi Host object from the vCenter inventory using the host name
"""
def get_host_object_from_vc(vc_rootFolder, target_host_name):
    # http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png
    for dc in vc_rootFolder.childEntity:
        for cl in dc.hostFolder.childEntity:
            for host in cl.host:
                if host.name == target_host_name:
                    return host
    return None


"""
Retrive Cluster object from the vCenter inventory using the cluster name
"""
def get_cluster_object_from_vc(vc_rootFolder, target_cluster_name):
    # http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png
    for dc in vc_rootFolder.childEntity:
        for cl in dc.hostFolder.childEntity:
            if cl.name == target_cluster_name:
                return cl
    return None

"""
Move an ESXi Host from its cluster to another cluster under the same vCenter
"""
def move_host_to_another_cluster(host, dest_cluster):
    # ESXi Host enters Maintenance Mode
    host.EnterMaintenanceMode(timeout=0, evacuatePoweredOffVms=True, maintenanceSpec=None)
    while not host.runtime.inMaintenanceMode:
        time.sleep(1)
    print("ESXi Host '%s' entered in Maintenance Mode successfully!" % host.name)

    # Move the ESXi Host to the target Cluster
    task_movehost = dest_cluster.MoveHostInto(host=host, resourcePool=None)
    while str(task_movehost.info.state) == "running": #TODO: better condition
        time.sleep(1)
    if str(task_movehost.info.state) != "success":
        raise SystemExit("ABORT: Moving ESXi Host '%s' to cluster '%s' failed" % (host.name, dest_cluster.name))
    print("Host '%s' moved successfully to Cluster '%s'!" % (host.name, dest_cluster.name))

    # ESXi Host exits Maintenance Mode
    host.ExitMaintenanceMode(timeout=0)
    while host.runtime.inMaintenanceMode:
        time.sleep(1)
    print("ESXi Host '%s' exited Maintenance Mode successfully!" % host.name)


"""
Add a standalone ESXi Host to a cluster by using the host IP Address
"""
def add_standalone_esxi_host(vc_rootFolder, host_ip, hostUserName, hostPassword, dest_cluster):
    # Define the Host Connect Spec
    connect_spec = vim.host.ConnectSpec(
        hostName=host_ip,  # DNS name or IP address of the host
        port=443,
        sslThumbprint=get_host_ssl_thumbprint(host_ip),  # Host SSL thumbprint
        userName=hostUserName,  # administration account on the host
        password=hostPassword,  # administration account on the host
        vmFolder=None,
        force=False,
        vimAccountName=None,  # account to be used for accessing the virtual machine files on the disk
        vimAccountPassword=None,  # account to be used for accessing the virtual machine files on the disk
        managementIp=None,  # IP address of the vC that will manage this host if different than connection
    )
    # Add the host to the destination cluster
    task_addhost = dest_cluster.AddHost(spec=connect_spec, asConnected=True, resourcePool=None, license=None)
    while str(task_addhost.info.state) == "running": #TODO: better condition
        time.sleep(1)
    if str(task_addhost.info.state) != "success":
        raise SystemExit("ABORT: Adding ESXi Host '%s' to vCenter failed" % host_ip)

    # Get Host object once added to the cluster
    host = get_host_object_from_vc(vc_rootFolder, host_ip)
    if host:
        print("Host '%s' successfully added to Cluster '%s'!" % (host_ip, dest_cluster.name))
    else:
        raise SystemExit("ABORT: Adding ESXi Host '%s' to vCenter failed" % host_ip)

    # Check if reconfiguration is needed for vSAN
    vsan_ready = is_host_vsan_ready(host)
    if not vsan_ready:
        # Enable connection to vSAN network for the Host
        configure_host_network_for_vsan(host)


"""
Get the SSL Thumprint from an ESXi Host using openssl without host password needed
-> http://www.virtuallyghetto.com/2012/04/extracting-ssl-thumbprint-from-esxi.html
"""
def get_host_ssl_thumbprint(host_ip):
    #TODO: actual command is:
    # "echo -n | openssl s_client -connect host_ip:443 2>/dev/null | openssl x509 -noout -fingerprint -sha1"
    # => currently used version will print extra output in logs
    open_ssl_cmd = "echo -n | openssl s_client -connect %s:443 | openssl x509 -noout -fingerprint -sha1" % host_ip
    inter_cmds = open_ssl_cmd.split("|")
    try:
        ps1 = subprocess.Popen(inter_cmds[0].split(), stdout=subprocess.PIPE)
        ps2 = subprocess.Popen(inter_cmds[1].split(), stdin=ps1.stdout, stdout=subprocess.PIPE)
        ps3 = subprocess.check_output(inter_cmds[2].split(), stdin=ps2.stdout)
        ssl_thumbprint = ps3.split("=")[1]
    except:
        raise SystemExit("ABORT: SSL Thumprint retrieval for ESXi Host %s failed" % host_ip)
    if ssl_thumbprint is None or len(ssl_thumbprint.split(':')) is not 20:
        raise SystemExit("ABORT: SSL Thumprint retrieval for ESXi Host %s failed" % host_ip)
    return ssl_thumbprint


"""
Check if the ESXi Host has:
    - vSAN enabled
    - its network interface ready to connect to a vSAN cluster
"""
def is_host_vsan_ready(host):
    if host.config.vsanHostConfig.enabled is True:
        if host.config.vsanHostConfig.networkInfo.port:
            if host.config.vsanHostConfig.networkInfo.port[0].device:
                return True
    return False


"""
Configure the ESXi Host network to enable connection to vSAN cluster
-> enabling the vSAN service in the Properties of the VMKernel
"""
def configure_host_network_for_vsan(host):
    # Get VMkernel (~ VirtualNIC) object from the host
    if host.config.network.vnic:
        vm_kernel = host.config.network.vnic[0].device

    # https://github.com/vmware/pyvmomi/blob/master/docs/vim/vsan/host/ConfigInfo.rst
    # Define the new network configuration
    new_vsan_port = vim.vsan.host.ConfigInfo.NetworkInfo.PortConfig(
                ipConfig=None,
                device=vm_kernel.device,  # Device name of the VMkernel used for vSAN
    )
    # Define new vSAN configuration for the ESXi Host
    vsan_config = vim.vsan.host.ConfigInfo(
            enabled=True,  # vSAN service is currently enabled on this host
            hostSystem=host,  # Host
            clusterInfo=None,  # vSAN storage configuration for this host -> not needed
            networkInfo=vim.vsan.host.ConfigInfo.NetworkInfo(port=[new_vsan_port]),  # vSAN network configuration for this host
    )
    # https://github.com/vmware/pyvmomi/blob/master/docs/vim/host/VsanSystem.rst
    # Update the ESXi Host with its new vSAN configuration
    host.configManager.vsanSystem.UpdateVsan_Task(vsan_config)




