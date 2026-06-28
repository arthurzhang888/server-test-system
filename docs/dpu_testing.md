# BF3/BF4 DPU 测试指南

NVIDIA BlueField DPU (Data Processing Unit) 是智能网卡，集成 ARM 核心、内存和硬件加速器。

## 支持的 DPU 型号

| 型号 | PCI ID | 网络速率 | ARM 核心 | 典型配置 |
|------|--------|----------|----------|----------|
| BF3 (BlueField-3) | 0xa2dc, 0xa2dd | 200Gbps | 8-16核 | MBF3H516A-CEEOT |
| BF4 (BlueField-4) | 待发布 | 400Gbps | 待发布 | - |

## 检测方式

### 1. 基础检测 (已集成)

```python
from src.detectors import DPUDetector

# 检测 DPU
detector = DPUDetector()
result = detector.detect()

print(f"DPU 存在: {result['present']}")
print(f"设备数量: {result['device_count']}")

for device in result['devices']:
    print(f"  - {device['model']} ({device['pci_slot']})")
    print(f"    固件: {device['firmware_version']}")
    print(f"    模式: {device['mode']}")  # dpu / nic
    print(f"    ARM: {device['arm_cores']}核, {device['arm_memory_gb']}GB")
```

### 2. 检测内容

#### 基础信息
- **PCI 设备**: 通过 `lspci` 枚举 Mellanox/NVIDIA 设备
- **固件版本**: 通过 `mstflint` 或 `mlxfwmanager` 读取
- **产品型号**: 通过 PSID 识别具体型号

#### 运行模式
- **DPU 模式**: ARM 核心运行独立 OS，具备完整功能
- **NIC 模式**: 作为普通网卡使用，ARM 核心不激活

#### 网络接口
- 物理端口 (p0, p1)
- OVS/OVN 加速接口
- SR-IOV VF 接口

#### 加速器
- **Crypto**: IPsec/TLS 硬件卸载
- **Compression**: 压缩/解压缩加速
- **Regex**: 正则表达式加速 (BF3)

#### 健康状态
- 温度监控 (通过 hwmon/sysfs)
- 功耗读取
- 风扇转速

### 3. 检测工具依赖

```bash
# 必需工具
sudo apt install lspci iproute2

# Mellanox 工具 (推荐)
# 下载地址: https://network.nvidia.com/products/adapter-software/firmware-tools/
sudo apt install mstflint mlxfwmanager

# DPU 开发工具 (用于深度测试)
# 从 NVIDIA DOCA SDK 安装
```

## DPU 功能测试

### 网络吞吐量测试

```bash
# 在 Host 端测试 DPU 物理端口
ethtool p0
ip link set p0 up

# 使用 iperf3 测试
iperf3 -c <dpu_ip> -p 5201 -t 60
```

### OVS 硬件卸载验证

```bash
# 检查 OVS 是否启用硬件卸载
ovs-vsctl get Open_vSwitch . other_config:hw-offload

# 查看流表卸载状态
ovs-appctl dpctl/dump-flows type=offloaded
```

### RDMA 测试

```bash
# 在 DPU 上启动服务端
ib_write_bw -d mlx5_0

# 在 Host 端连接测试
ib_write_bw -d mlx5_0 <dpu_ip>
```

### DPU ARM 核心访问

```bash
# 通过 rshim 访问 DPU console
screen /dev/rshim0/console 115200

# 查看 DPU 内部状态
cat /dev/rshim0/misc
```

## 压力测试

### 基础压力测试 (Host 侧)

```python
from src.stress_tests import DPUStressTest

# 创建压力测试
stress = DPUStressTest(
    duration=300,  # 5分钟
    network_load=True,
    crypto_load=True
)

# 运行测试
result = stress.run()

print(f"测试状态: {result['status']}")
print(f"最高温度: {result['max_temperature_c']}°C")
print(f"平均吞吐量: {result['avg_throughput_gbps']} Gbps")
```

### DPU 内部压力测试

需要在 DPU ARM 核心上运行:

```bash
# 在 DPU 上安装 doca 工具
# 运行内部压力测试
doca_stress_test --duration 300 --cpu-load 100 --memory-load 80
```

## 故障排查

### DPU 未被检测到

```bash
# 检查 PCI 设备
lspci | grep -i mellanox
lspci | grep -i nvidia

# 检查设备 ID
lspci -nn | grep 15b3

# 查看内核模块
lsmod | grep mlx
```

### 固件读取失败

```bash
# 安装 Mellanox 工具
wget https://content.mellanox.com/MFT/mft-4.26.0-93-x86_64-deb.tgz
tar xzf mft-4.26.0-93-x86_64-deb.tgz
sudo ./install.sh

# 启动 MST 服务
sudo mst start

# 查询设备
sudo mst status
sudo flint -d /dev/mst/mt41692_pciconf0 q
```

### 温度读取失败

```bash
# 手动检查 hwmon
ls /sys/class/hwmon/
cat /sys/class/hwmon/hwmon*/name
cat /sys/class/hwmon/hwmon*/temp1_input

# 检查权限
sudo chmod 644 /sys/class/hwmon/hwmon*/temp1_input
```

## 配置示例

```yaml
# config/server_types/ai_server.yaml
server_type: ai_server
tests:
  - name: dpu_test
    required: true
    params:
      check_bf3: true
      check_bf4: false  # 如果系统只有 BF3
      min_firmware_version: "32.38.1000"
      require_dpu_mode: true  # 要求 DPU 模式，非 NIC 模式
      accelerators:
        - crypto
        - compression
  - name: dpu_stress
    required: false
    params:
      duration: 300
      max_temperature: 85
      min_throughput_gbps: 180
```

## 参考资料

- [NVIDIA BlueField-3 DPU 文档](https://docs.nvidia.com/dpu/bluefield3/)
- [NVIDIA DOCA SDK](https://developer.nvidia.com/networking/doca)
- [MFT (Mellanox Firmware Tools)](https://network.nvidia.com/products/adapter-software/firmware-tools/)
