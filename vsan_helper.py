from pyVmomi import vim
import time

"""
Check if the ESXi Host has:
    - vSAN enabled
    - its network interface ready to connect to a vSAN cluster
"""
def is_host_vsan_ready(host):
    # if host.config.vsanHostConfig.enabled is True:
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
        vm_kernel = host.config.network.vnic[0]

    # Define the new network configuration
    new_vsan_port = vim.vsan.host.ConfigInfo.NetworkInfo.PortConfig(
                ipConfig=None,
                device=vm_kernel.device,  # Device name of the VMkernel used for vSAN
    )

    # Define new vSAN configuration for the ESXi Host
    vsan_config = vim.vsan.host.ConfigInfo(
            enabled=False,  # Should NOT be set to True before being added to a vSAN cluster
            hostSystem=host,  # Host
            clusterInfo=None,  # vSAN storage configuration for this host -> not needed
            networkInfo=vim.vsan.host.ConfigInfo.NetworkInfo(port=[new_vsan_port]),  # vSAN network configuration for this host
    )

    # Update the ESXi Host with its new vSAN configuration
    task_vsan = host.configManager.vsanSystem.UpdateVsan_Task(vsan_config)
    while task_vsan.info.state == vim.TaskInfo.State.running:
        time.sleep(1)
    if task_vsan.info.state != vim.TaskInfo.State.success:
        raise SystemExit("ABORT: ESXi Host '%s' failed to reconfigure its network in attempt to join vSAN cluster" % host.name)
    print("ESXi Host '%s' successfully reconfigured its network to be able to join vSAN cluster!" % host.name)


"""
To test the connection between an ESXi Host and a vSAN cluster:
    try to deploy a VM on this host for Compute  & 'vsanDatastore' for Storage
"""
def deploy_vm_to_test_vsan_connection(host):
    return
