# CIS Level 1 Compliance - Action1 Data Source (Windows only)
#
# Data Sources in Action1 can ONLY be PowerShell (the create/update API's "language" field has
# a hard enum: ["PowerShell"], nothing else is legal), and Action1's own Linux/macOS agent
# scripts use Bash instead of PowerShell (confirmed from the built-in "Deploy Linux Package" /
# "Reboot macOS endpoint" Scripts). So a Data Source will never run on a Linux/macOS endpoint no
# matter what's inside it - there is no cross-platform path through this mechanism. For
# Linux/macOS coverage, see reports/run_bash_check_via_automation.py instead (Bash Script run
# via an Automation, results pulled through the Automation Instance API into the external
# generate_compliance_report.py - it can't populate a native Console report, only Data
# Sources can do that).

function Get-CheckResult {
    param(
        [Parameter(Mandatory)][scriptblock]$Test
    )
    try {
        $findings = @(& $Test)
        if ($findings.Count -eq 0) {
            return [PSCustomObject]@{ Status = 'Pass'; Findings = '' }
        }
        return [PSCustomObject]@{ Status = 'Fail'; Findings = ($findings -join ' | ') }
    }
    catch {
        return [PSCustomObject]@{ Status = 'Error'; Findings = $_.Exception.Message }
    }
}

function Get-OSVersionString {
    try {
        $caption = (Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop).Caption
        if ($caption) { return $caption.Trim() }
    }
    catch {}
    return [System.Environment]::OSVersion.VersionString
}

$results = [ordered]@{}

$results['Local Admins'] = Get-CheckResult -Test {
    # Group by well-known SID (S-1-5-32-544), not by name 'Administrators' - the name is
    # localized on non-English Windows installs and Get-LocalGroupMember -Group would fail.
    $findings = @()
    $builtIn = Get-LocalUser | Where-Object { $_.SID -like '*-500' }
    if ($builtIn -and $builtIn.Enabled) { $findings += 'Built-in Administrator account is ENABLED' }
    $adminsGroup = Get-LocalGroup -SID 'S-1-5-32-544' -ErrorAction Stop
    $adminCount = @(Get-LocalGroupMember -SID $adminsGroup.SID -ErrorAction Stop | Where-Object { $_.ObjectClass -eq 'User' }).Count
    if ($adminCount -gt 3) { $findings += "High local admin count: $adminCount" }
    $findings
}

$results['Password Policy'] = Get-CheckResult -Test {
    $findings = @()
    $net = net accounts 2>&1 | Out-String
    if ($net -match 'Minimum password length\s+(\d+)') {
        if ([int]$Matches[1] -lt 14) { $findings += "Min password length is $($Matches[1]), expected >= 14" }
    }
    if ($net -match 'Lockout threshold\s+(\S+)') {
        if ($Matches[1] -eq 'Never' -or [int]$Matches[1] -eq 0) { $findings += 'Account lockout threshold is disabled' }
    }
    $findings
}

$results['Firewall'] = Get-CheckResult -Test {
    $findings = @()
    foreach ($p in Get-NetFirewallProfile) {
        if (-not $p.Enabled) { $findings += "$($p.Name) profile disabled" }
        if ($p.DefaultInboundAction -ne 'Block') { $findings += "$($p.Name) default inbound is not Block" }
    }
    $findings
}

$results['BitLocker'] = Get-CheckResult -Test {
    $findings = @()
    $volumes = Get-BitLockerVolume -ErrorAction Stop | Where-Object { $_.VolumeType -eq 'OperatingSystem' -or $_.VolumeType -eq 'Data' }
    foreach ($v in $volumes) {
        if ($v.ProtectionStatus -ne 'On') { $findings += "Volume $($v.MountPoint) is not encrypted" }
    }
    $findings
}

$results['RDP Exposure'] = Get-CheckResult -Test {
    $findings = @()
    $rdpEnabled = (Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections -eq 0
    if ($rdpEnabled) {
        $nla = (Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name UserAuthentication -ErrorAction SilentlyContinue).UserAuthentication
        if ($nla -ne 1) { $findings += 'RDP is enabled without Network Level Authentication' }
        $anyRule = Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue | Where-Object { $_.Enabled -eq 'True' } |
            Get-NetFirewallAddressFilter | Where-Object { $_.RemoteAddress -eq 'Any' }
        if ($anyRule) { $findings += 'RDP firewall rule allows Any remote source' }
    }
    $findings
}

$results['Defender'] = Get-CheckResult -Test {
    $findings = @()
    $mp = Get-MpComputerStatus -ErrorAction Stop
    if (-not $mp.RealTimeProtectionEnabled) { $findings += 'Real-time protection disabled' }
    if ($mp.AntivirusSignatureAge -gt 7) { $findings += "AV signatures $($mp.AntivirusSignatureAge) days old" }
    $findings
}

$results['USB Storage'] = Get-CheckResult -Test {
    $findings = @()
    $usbstor = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\USBSTOR' -Name Start -ErrorAction SilentlyContinue).Start
    $denyAll = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices' -Name 'Deny_All' -ErrorAction SilentlyContinue).Deny_All
    if ($usbstor -ne 4 -and $denyAll -ne 1) { $findings += 'Removable USB storage is not restricted' }
    $findings
}

$passed = @($results.Values | Where-Object { $_.Status -eq 'Pass' }).Count
$applicable = @($results.Values | Where-Object { $_.Status -ne 'NotApplicable' }).Count
$compliancePercent = if ($applicable -gt 0) { [math]::Round(($passed / $applicable) * 100, 1) } else { 0 }

$output = [PSCustomObject]@{
    'OS Platform'                 = 'Windows'
    'OS Version'                  = Get-OSVersionString
    'Overall Compliance %'        = $compliancePercent
    'Local Admins Status'         = $results['Local Admins'].Status
    'Local Admins Findings'       = $results['Local Admins'].Findings
    'Password Policy Status'      = $results['Password Policy'].Status
    'Password Policy Findings'    = $results['Password Policy'].Findings
    'Firewall Status'             = $results['Firewall'].Status
    'Firewall Findings'           = $results['Firewall'].Findings
    'BitLocker Status'            = $results['BitLocker'].Status
    'BitLocker Findings'          = $results['BitLocker'].Findings
    'RDP Exposure Status'         = $results['RDP Exposure'].Status
    'RDP Exposure Findings'       = $results['RDP Exposure'].Findings
    'Defender Status'             = $results['Defender'].Status
    'Defender Findings'           = $results['Defender'].Findings
    'USB Storage Status'          = $results['USB Storage'].Status
    'USB Storage Findings'        = $results['USB Storage'].Findings
    'Scan Timestamp'              = (Get-Date).ToUniversalTime().ToString('o')
}

$output
