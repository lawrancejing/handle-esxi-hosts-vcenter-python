from pyVmomi import vim
import time
import subprocess
import vsan_helper
import vcenter_helper
import os

"""
Retrieve ESXi Host object from the vCenter inventory using the host name
"""
def get_host_object_from_vc(vc_serviceInstance, target_host_name):
    # http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png
    vc_rootFolder = vc_serviceInstance.RetrieveContent().rootFolder
    for dc in vc_rootFolder.childEntity:
        for cl in dc.hostFolder.childEntity:
            for host in cl.host:
                if host.name == target_host_name:
                    return host
    return None


"""
Retrieve ESXi Host object from the vCenter inventory using the host IPv4 Address
"""
def get_host_by_ip_address(vc_serviceInstance, target_ip_address):
    # http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png
    vc_rootFolder = vc_serviceInstance.RetrieveContent().rootFolder
    for dc in vc_rootFolder.childEntity:
        for cl in dc.hostFolder.childEntity:
            for host in cl.host:
                if host.config.network.vnic and host.config.network.vnic[0].spec.ip.ipAddress == target_ip_address:
                    return host
    return None


"""
Retrieve Cluster object from the vCenter inventory using the cluster name
"""
def get_cluster_object_from_vc(vc_serviceInstance, target_cluster_name):
    # http://vmware.github.io/pyvmomi-community-samples/images/vchierarchy.png
    vc_rootFolder = vc_serviceInstance.RetrieveContent().rootFolder
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
    while task_movehost.info.state == vim.TaskInfo.State.running:
        time.sleep(1)
    if task_movehost.info.state != vim.TaskInfo.State.success:
        raise SystemExit("ABORT: Moving ESXi Host '%s' to cluster '%s' failed" % (host.name, dest_cluster.name))
    print("ESXi Host '%s' moved successfully to Cluster '%s'!" % (host.name, dest_cluster.name))

    # ESXi Host exits Maintenance Mode
    host.ExitMaintenanceMode(timeout=0)
    while host.runtime.inMaintenanceMode:
        time.sleep(1)
    print("ESXi Host '%s' exited Maintenance Mode successfully!" % host.name)


"""
Pre configure a standalone ESXi Host (datastore, vSAN service enablement,...) before attempting to add the host to a cluster
"""
def pre_configure_esxi_host(host_ip, hostUserName, hostPassword, cluster_vsan_enabled=False):
    # Get Host object using its IPv4 Address
    host_si = vcenter_helper.create_connection_to_endpoint(ip_address=host_ip, username=hostUserName, password=hostPassword)
    host = get_host_by_ip_address(vc_serviceInstance=host_si, target_ip_address=host_ip)

    # Reconfigure the Host network interface if need be for vSAN
    if cluster_vsan_enabled:
        # Check if reconfiguration is needed to have vSAN enabled
        vsan_ready = vsan_helper.is_host_vsan_ready(host)
        if not vsan_ready:
            # Enable connection to vSAN network for the Host
            vsan_helper.configure_host_network_for_vsan(host)

    # Destroy all local datastores on the ESXi Host
    # Special use case: using ONLY vSAN datastore & datastore URL conflicts between standalone ESXi hosts created
    for ds in host.datastore:
        ds.DestroyDatastore()
    print("Initial reconfiguration of standalone ESXi Host '%s' succeeded!" % host_ip)


"""
Add a standalone ESXi Host to a cluster by using the host IP Address
"""
def add_standalone_esxi_host(vc_serviceInstance, host_ip, hostUserName, hostPassword, dest_cluster, cluster_vsan_enabled=False):
    # Apply initial configuration on ESXi Host before attempting to add it to an actual Cluster
    pre_configure_esxi_host(host_ip, hostUserName, hostPassword, cluster_vsan_enabled)

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
    while task_addhost.info.state == vim.TaskInfo.State.running:
        time.sleep(1)
    if task_addhost.info.state != vim.TaskInfo.State.success:
        raise SystemExit("ABORT: Adding ESXi Host '%s' to vCenter failed" % host_ip)

    # Get Host object once added to the cluster
    host = get_host_object_from_vc(vc_serviceInstance, host_ip)
    if host:
        print("ESXi Host '%s' successfully added to Cluster '%s'!" % (host_ip, dest_cluster.name))
    else:
        raise SystemExit("ABORT: Adding ESXi Host '%s' to vCenter failed" % host_ip)

    # Force vSphere HA reconfiguration on the ESXi Host
    trigger_vsphereHA_reconfigure(host)


"""
Get the SSL Thumprint from an ESXi Host using openssl without host password needed
-> http://www.virtuallyghetto.com/2012/04/extracting-ssl-thumbprint-from-esxi.html
"""
def get_host_ssl_thumbprint(host_ip):
    open_ssl_cmd = "echo -n | openssl s_client -connect %s:443 | openssl x509 -noout -fingerprint -sha1" % host_ip
    inter_cmds = open_ssl_cmd.split("|")
    try:
        ps1 = subprocess.Popen(inter_cmds[0].split(), stdout=subprocess.PIPE)
        FNULL = open(os.devnull, 'w')  # equivalent of /dev/null
        ps2 = subprocess.Popen(inter_cmds[1].split(), stdin=ps1.stdout, stdout=subprocess.PIPE, stderr=FNULL)
        ps3 = subprocess.check_output(inter_cmds[2].split(), stdin=ps2.stdout)
        ssl_thumbprint = ps3.split("=")[1].strip()
    except:
        raise SystemExit("ABORT: SSL Thumprint retrieval for ESXi Host %s failed" % host_ip)
    if ssl_thumbprint is None or len(ssl_thumbprint.split(':')) is not 20:
        raise SystemExit("ABORT: SSL Thumprint retrieval for ESXi Host %s failed" % host_ip)
    print("SSL Thumbprint for host '%s': '%s'" % (host_ip, ssl_thumbprint))
    return ssl_thumbprint


"""
Trigger vSphere HA reconfiguration on ESXi Host
"""
def trigger_vsphereHA_reconfigure(host):
    task_reconfigureHA = host.ReconfigureDAS()
    while task_reconfigureHA.info.state == vim.TaskInfo.State.running:
        time.sleep(1)
    if task_reconfigureHA.info.state != vim.TaskInfo.State.success:
        raise SystemExit("ABORT: ESXi Host '%s' failed to reconfigure for HA" % host.name)
    print("ESXi Host '%s' successfully reconfigured for HA!" % host.name)


"""
Wait for all the tasks running on an entity (host,cluster) to complete
"""
def wait_for_running_task_on_entity_to_complete(entity):
    while any(t.info.state == vim.TaskInfo.State.running for t in entity.recentTask):
        time.sleep(10)
        print("At least 1 task is still running on the entity named '%s', keep waiting...\n" % entity.name)
    print("No more running task on the entity named '%s'!" % entity.name)


"""
Remove an ESXi Host from the vCenter Inventory
"""
def remove_host_from_vc_inventory(host):
    host_name = host.name
    # ESXi Host enters Maintenance Mode
    host.EnterMaintenanceMode(timeout=0, evacuatePoweredOffVms=True, maintenanceSpec=None)
    while not host.runtime.inMaintenanceMode:
        time.sleep(1)
    print("ESXi Host '%s' entered in Maintenance Mode successfully!" % host_name)

    # Destroy ESXi Host
    task_destroyhost = host.Destroy()
    while task_destroyhost.info.state == vim.TaskInfo.State.running:
        time.sleep(1)
    if task_destroyhost.info.state != vim.TaskInfo.State.success:
        raise SystemExit("ABORT: ESXi Host '%s' failed to be removed from the vC inventory" % host_name)
    print("ESXi Host '%s' removed from the vC inventory!" % host_name)
