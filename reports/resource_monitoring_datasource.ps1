# Resource Monitoring - Action1 Data Source (cross-platform)
#
# Disk / memory free space, since Action1's own built-in data sources for this
# ("Disks Summary", "Process/Memory Stats") are Windows-only (Get-WmiObject Win32_Volume /
# Win32_OperatingSystem - neither exists on Linux/macOS, and neither branches by OS). No CPU
# utilization column: Action1 doesn't track that anywhere as a point-in-time inventory field
# (nor does any built-in data source), and a single instantaneous sample from a periodic scan
# is a poor proxy for load anyway - that's a live-monitoring concern, not a scan snapshot one.

$onWindows = -not (Test-Path Variable:IsWindows) -or $IsWindows
$onLinux   = (Test-Path Variable:IsLinux) -and $IsLinux
$onMacOS   = (Test-Path Variable:IsMacOS) -and $IsMacOS

$LowDiskThresholdPercent   = 15
$LowMemoryThresholdPercent = 10

#
# Disk - [System.IO.DriveInfo] is a .NET primitive available on every platform pwsh runs on,
# so this needs no per-OS branching at all.
#
$systemDrivePath = if ($onWindows) { $env:SystemDrive + '\' } else { '/' }
$diskStatus = 'Unknown'
$diskFindings = ''
$totalGb = ''
$freeGb = ''
$percentFree = ''

try {
    $drive = [System.IO.DriveInfo]::new($systemDrivePath)
    if ($drive.IsReady) {
        $totalGb = [math]::Round($drive.TotalSize / 1GB, 1)
        $freeGb = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
        $percentFree = if ($drive.TotalSize -gt 0) { [math]::Round(($drive.AvailableFreeSpace / $drive.TotalSize) * 100, 1) } else { 0 }
        if ($percentFree -lt $LowDiskThresholdPercent) {
            $diskStatus = 'Fail'
            $diskFindings = "System drive has $percentFree% free space, below $LowDiskThresholdPercent% threshold"
        }
        else {
            $diskStatus = 'Pass'
        }
    }
    else {
        $diskStatus = 'Error'
        $diskFindings = "Drive $systemDrivePath is not ready"
    }
}
catch {
    $diskStatus = 'Error'
    $diskFindings = $_.Exception.Message
}

#
# Memory - genuinely platform-specific; no cross-platform .NET equivalent to DriveInfo exists
# for this.
#
$memStatus = 'Unknown'
$memFindings = ''
$memTotalGb = ''
$memFreeGb = ''
$memPercentFree = ''

try {
    if ($onWindows) {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        $memTotalGb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)   # KB -> GB
        $memFreeGb = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    }
    elseif ($onLinux) {
        $meminfo = Get-Content '/proc/meminfo' -ErrorAction Stop
        $totalLine = $meminfo | Where-Object { $_ -match '^MemTotal:\s+(\d+)' }
        # [int64], not [int]: MemTotal in KiB exceeds Int32's ~2 billion ceiling above ~2TiB RAM.
        $totalKb = if ($totalLine) { [int64](($totalLine -replace '\D', ' ') -split '\s+' | Where-Object { $_ })[0] } else { 0 }
        $availLine = $meminfo | Where-Object { $_ -match '^MemAvailable:\s+(\d+)' }
        $availKb = if ($availLine) { [int64](($availLine -replace '\D', ' ') -split '\s+' | Where-Object { $_ })[0] } else { 0 }
        $memTotalGb = [math]::Round($totalKb / 1MB, 1)
        $memFreeGb = [math]::Round($availKb / 1MB, 1)
    }
    elseif ($onMacOS) {
        $totalBytes = [int64]((sysctl -n hw.memsize 2>&1) -join '')
        $pageSize = [int]((sysctl -n hw.pagesize 2>&1) -join '')
        $vmStat = (vm_stat 2>&1) -join "`n"
        $freePages = 0
        if ($vmStat -match 'Pages free:\s+(\d+)\.') { $freePages += [int]$Matches[1] }
        if ($vmStat -match 'Pages inactive:\s+(\d+)\.') { $freePages += [int]$Matches[1] }
        $memTotalGb = [math]::Round($totalBytes / 1GB, 1)
        $memFreeGb = [math]::Round(($freePages * $pageSize) / 1GB, 1)
    }

    if ($memTotalGb -ne '' -and $memTotalGb -gt 0) {
        $memPercentFree = [math]::Round(($memFreeGb / $memTotalGb) * 100, 1)
        if ($memPercentFree -lt $LowMemoryThresholdPercent) {
            $memStatus = 'Fail'
            $memFindings = "$memPercentFree% memory free, below $LowMemoryThresholdPercent% threshold"
        }
        else {
            $memStatus = 'Pass'
        }
    }
}
catch {
    $memStatus = 'Error'
    $memFindings = $_.Exception.Message
}

$osPlatform = if ($onWindows) { 'Windows' } elseif ($onLinux) { 'Linux' } elseif ($onMacOS) { 'macOS' } else { 'Unknown' }

$output = [PSCustomObject]@{
    'OS Platform'             = $osPlatform
    'Disk Status'             = $diskStatus
    'Disk Findings'           = $diskFindings
    'Disk Total (Gb)'         = $totalGb
    'Disk Free (Gb)'          = $freeGb
    'Disk Percent Free (%)'   = $percentFree
    'Memory Status'           = $memStatus
    'Memory Findings'         = $memFindings
    'Memory Total (Gb)'       = $memTotalGb
    'Memory Free (Gb)'        = $memFreeGb
    'Memory Percent Free (%)' = $memPercentFree
    'Scan Timestamp'          = (Get-Date).ToUniversalTime().ToString('o')
}

$output
