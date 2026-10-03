# CIS Controls v8 - Action1 Data Source (Windows, PowerShell 5.1+)
#
# One row per endpoint, one column per control: 'Pass', 'Manual', or 'Fail: <reason>' / 'Error: <reason>'. Only the endpoint-measurable
# safeguards (mostly IG1) are checked; organisational controls (training, vendors, incident
# response, pentests...) can't be seen from an endpoint and are reported as 'Manual'.
# CIS Score % = passed / measured (Manual excluded).
#
# Report columns carry only a short reason (first 100 chars) - Action1 truncates values at 255
# chars and silently drops rows from data sources with more than 30 columns. The full result - every finding of
# every control - is written as JSON to $DetailsFile on the endpoint; its path is in the
# 'Details File' column. Collecting those files is a separate job; this script only produces data.
#
# Requires: runs as SYSTEM via the Action1 agent (secedit/auditpol need admin).

# Any failure inside a check must surface as 'Error', not as a bogus Fail/Pass built from empty data.
$ErrorActionPreference = 'Stop'

$DetailsFile = Join-Path $env:ProgramData 'CISReports\cis_controls_v8.json'

$status = [ordered]@{}   # Pass / Fail / Error / Manual
$full = [ordered]@{}     # every finding, for $DetailsFile

# Action1 truncates report values at 255 chars; keep columns short, full text goes to $DetailsFile.
function Limit-Text([string]$Text) {
    if ($Text.Length -le 100) { return $Text }
    return $Text.Substring(0, 97) + '...'
}

function Test-Control {
    param([string]$Column, [string]$Tag, [scriptblock]$Test)
    try {
        $found = @(& $Test | Where-Object { $_ })
        $status[$Column] = if ($found.Count) { 'Fail' } else { 'Pass' }
        $full[$Column] = @($found | ForEach-Object { [string]$_ })
    }
    catch {
        $status[$Column] = 'Error'
        $full[$Column] = @($_.Exception.Message)
    }

}

# Local security policy, locale-independent (net accounts output is localized).
$secPolicy = @{}
try {
    $cfg = Join-Path $env:TEMP "a1_secpol_$PID.inf"
    secedit /export /cfg $cfg /areas SECURITYPOLICY /quiet | Out-Null
    if (Test-Path $cfg) { foreach ($line in Get-Content $cfg) {
        if ($line -match '^\s*(\w+)\s*=\s*(.+?)\s*$') { $secPolicy[$Matches[1]] = $Matches[2] }
    } }
    Remove-Item $cfg -Force -ErrorAction SilentlyContinue
}
catch {}

$os = Get-CimInstance Win32_OperatingSystem
$users = @(Get-LocalUser)

# 1 Inventory and Control of Enterprise Assets - 1.1: the agent reporting this row is the inventory.
Test-Control 'CIS 01 Enterprise Assets' '01' { }

# 2 Inventory and Control of Software Assets - 2.2: authorized software is currently supported.
Test-Control 'CIS 02 Software Assets' '02' {
    if ($os.Caption -match 'XP|Vista|Windows 7|Windows 8|2003|2008|2012') { "Unsupported OS: $($os.Caption)" }
    elseif ($os.Caption -match 'Windows 10' -and [int]$os.BuildNumber -lt 19045) { "Windows 10 build $($os.BuildNumber) is out of support" }
}

# 3 Data Protection - 3.6 encrypt end-user devices; 3.9 encrypt/restrict removable media.
Test-Control 'CIS 03 Data Protection' '03' {
    if (-not (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue)) {
        'BitLocker feature is not installed - volumes are not encrypted'
    }
    else {
        Get-BitLockerVolume -ErrorAction Stop | Where-Object { $_.VolumeType -in 'OperatingSystem', 'Data' -and $_.ProtectionStatus -ne 'On' } |
            ForEach-Object { "Volume $($_.MountPoint) is not encrypted" }
    }
    $usbstor = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR' -Name Start -ErrorAction SilentlyContinue).Start
    $denyAll = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices' -Name Deny_All -ErrorAction SilentlyContinue).Deny_All
    if ($usbstor -ne 4 -and $denyAll -ne 1) { 'Removable USB storage is not restricted' }
}

# 4 Secure Configuration - 4.3 session locking, 4.4/4.5 firewall, 4.7 default accounts, 4.8 unneeded services.
Test-Control 'CIS 04 Secure Configuration' '04' {
    $idle = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name InactivityTimeoutSecs -ErrorAction SilentlyContinue).InactivityTimeoutSecs
    if (-not $idle -or $idle -gt 900) { 'Machine inactivity lock is not set to 15 minutes or less' }
    foreach ($p in Get-NetFirewallProfile) {
        if (-not $p.Enabled) { "Firewall $($p.Name) profile disabled" }
        elseif ($p.DefaultInboundAction -ne 'Block') { "Firewall $($p.Name) default inbound is not Block" }
    }
    if ($users | Where-Object { $_.SID -like '*-500' -and $_.Enabled }) { 'Built-in Administrator account is enabled' }
    if ($users | Where-Object { $_.SID -like '*-501' -and $_.Enabled }) { 'Guest account is enabled' }
    if ((Get-SmbServerConfiguration).EnableSMB1Protocol) { 'SMBv1 is enabled' }
}

# 5 Account Management - 5.2 unique/strong passwords, 5.3 dormant accounts, 5.4 restrict admin rights.
Test-Control 'CIS 05 Account Management' '05' {
    if (-not $secPolicy.Count) { throw 'could not export local security policy (secedit)' }
    $minLen = [int]$secPolicy['MinimumPasswordLength']
    if ($minLen -lt 14) { "Minimum password length is $minLen (expected >= 14)" }
    $cutoff = (Get-Date).AddDays(-45)
    $users | Where-Object { $_.Enabled -and $_.LastLogon -and $_.LastLogon -lt $cutoff } |
        ForEach-Object { "Dormant enabled account: $($_.Name) (last logon $($_.LastLogon.ToString('yyyy-MM-dd')))" }
    $admins = @(Get-LocalGroupMember -SID 'S-1-5-32-544' | Where-Object { $_.ObjectClass -eq 'User' })
    if ($admins.Count -gt 3) { "High local admin count: $($admins.Count)" }
}

# 6 Access Control Management - 6.2 lockout of failed logons, 6.5-ish remote access hardening.
Test-Control 'CIS 06 Access Control' '06' {
    if (-not $secPolicy.Count) { throw 'could not export local security policy (secedit)' }
    $lockout = [int]$secPolicy['LockoutBadCount']
    if ($lockout -eq 0 -or $lockout -gt 5) { "Account lockout threshold is $lockout (expected 1-5)" }
    $ts = 'HKLM:\System\CurrentControlSet\Control\Terminal Server'
    if ((Get-ItemProperty $ts -Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections -eq 0) {
        if ((Get-ItemProperty "$ts\WinStations\RDP-Tcp" -Name UserAuthentication -ErrorAction SilentlyContinue).UserAuthentication -ne 1) {
            'RDP is enabled without Network Level Authentication'
        }
        $open = Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue | Where-Object { $_.Enabled -eq 'True' } |
            Get-NetFirewallAddressFilter | Where-Object { $_.RemoteAddress -eq 'Any' }
        if ($open) { 'RDP firewall rule allows any remote address' }
    }
}

# 7 Continuous Vulnerability Management - 7.3 automated OS patching (CVE/missing-update counts come
# from the Action1 API, not from here).
Test-Control 'CIS 07 Vulnerability Management' '07' {
    if ((Get-Service wuauserv -ErrorAction SilentlyContinue).StartType -eq 'Disabled') { 'Windows Update service is disabled' }
    $last = Get-HotFix | Where-Object { $_.InstalledOn } | Sort-Object InstalledOn -Descending | Select-Object -First 1
    if (-not $last) { 'No installed updates found' }
    elseif ($last.InstalledOn -lt (Get-Date).AddDays(-45)) { "Last update installed $($last.InstalledOn.ToString('yyyy-MM-dd')) (> 45 days ago)" }
}

# 8 Audit Log Management - 8.2 collect audit logs, 8.3 adequate log storage.
Test-Control 'CIS 08 Audit Log Management' '08' {
    # Logon subcategory by GUID (names are localized).
    # ponytail: 'No Auditing' match is English-only; a localized OS reports Fail-safe as audited.
    $raw = auditpol /get /subcategory:'{0CCE9215-69AE-11D9-BED3-505054503030}' /r
    if ($LASTEXITCODE) { throw "auditpol failed: $raw" }
    $logon = $raw | Where-Object { $_ } | ConvertFrom-Csv
    if (-not $logon -or $logon.'Inclusion Setting' -match 'No Auditing') { 'Logon events are not audited' }
    $size = (Get-WinEvent -ListLog Security).MaximumSizeInBytes
    if ($size -lt 196608KB) { "Security log max size is $([math]::Round($size / 1MB)) MB (expected >= 192 MB)" }
}

# 9 Email and Web Browser Protections - 9.x SmartScreen not turned off.
Test-Control 'CIS 09 Email and Browser' '09' {
    $ss = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System' -Name EnableSmartScreen -ErrorAction SilentlyContinue).EnableSmartScreen
    if ($ss -eq 0) { 'Windows SmartScreen is disabled by policy' }
}

# 10 Malware Defenses - 10.1 AV deployed, 10.2 auto signature updates, 10.3 autorun disabled.
Test-Control 'CIS 10 Malware Defenses' '10' {
    $mp = Get-MpComputerStatus -ErrorAction SilentlyContinue
    if (-not $mp) { 'Microsoft Defender not available - verify third-party anti-malware' }
    else {
        if (-not $mp.RealTimeProtectionEnabled) { 'Real-time protection disabled' }
        if ($mp.AntivirusSignatureAge -gt 7) { "AV signatures $($mp.AntivirusSignatureAge) days old" }
    }
    $exp = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer' -ErrorAction SilentlyContinue
    if ($exp.NoDriveTypeAutoRun -ne 255 -and $exp.NoAutorun -ne 1) { 'AutoRun is not disabled for all drives' }
}

# 11 Data Recovery - 11.2 automated backups.
# ponytail: heuristic - looks for a known backup agent service; can't see agentless/hypervisor backups.
Test-Control 'CIS 11 Data Recovery' '11' {
    $backup = Get-Service | Where-Object {
        $_.Status -eq 'Running' -and ($_.Name + ' ' + $_.DisplayName) -match 'Veeam|Acronis|Datto|Cohesity|Rubrik|Commvault|Veritas|Backup Exec|Carbonite|Altaro|Nakivo|Arcserve|Backblaze|Druva|MSP360|CloudBerry'
    }
    if (-not $backup) { 'No running backup agent detected' }
}

$manual = 'Manual'
$status['CIS 12 Network Infrastructure'] = $manual
$status['CIS 13 Network Monitoring'] = $manual
$status['CIS 14 Security Awareness'] = $manual
$status['CIS 15 Service Providers'] = $manual
$status['CIS 16 Application Security'] = $manual
$status['CIS 17 Incident Response'] = $manual
$status['CIS 18 Penetration Testing'] = $manual

$measured = @($status.Values | Where-Object { $_ -ne $manual })
$passed = @($measured | Where-Object { $_ -eq 'Pass' }).Count
$score = if ($measured.Count) { [math]::Round($passed / $measured.Count * 100, 1) } else { 0 }

$output = [ordered]@{
    'OS Version'  = $os.Caption
    'CIS Score %' = $score
}
foreach ($k in $status.Keys) {
    $output[$k] = if ($full[$k]) { Limit-Text ("$($status[$k]): " + ($full[$k] -join ' | ')) } else { $status[$k] }
}
$output['Scan Timestamp'] = (Get-Date).ToUniversalTime().ToString('o')

try {
    New-Item -ItemType Directory -Force (Split-Path $DetailsFile) | Out-Null
    [ordered]@{
        endpoint  = $env:COMPUTERNAME
        timestamp = $output['Scan Timestamp']
        os        = $os.Caption
        score     = $score
        controls  = @($status.Keys | ForEach-Object {
            [ordered]@{ control = $_; status = $status[$_]; findings = @($full[$_]) }
        })
    } | ConvertTo-Json -Depth 5 | Set-Content -Path $DetailsFile -Encoding UTF8
    $output['Details File'] = $DetailsFile
}
catch {
    $output['Details File'] = Limit-Text "not written: $($_.Exception.Message)"
}
# Required by Action1: unique row key per endpoint ('none' = one row). Not a report column.
$output['A1_Key'] = 'none'

[PSCustomObject]$output
