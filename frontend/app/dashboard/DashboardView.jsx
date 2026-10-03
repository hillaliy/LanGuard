import DashboardInsightCards from './DashboardInsightCards';
import DashboardStatusCards from './DashboardStatusCards';
import DashboardSummaryCards from './DashboardSummaryCards';

export default function DashboardView({
  counters,
  appSettings,
  networkRanges,
  networkRangeLabels,
  scanStatus,
  scanVisibility,
  timeZone,
  onOpenScanDetails,
  speedtestTrackerPayload,
  events,
  devices,
  onSelectDevice,
  onOpenAttentionDevices,
  onOpenRecentChanges,
  onError,
}) {
  return (
    <>
      <DashboardStatusCards counters={counters} />

      <DashboardSummaryCards
        appSettings={appSettings}
        counters={counters}
        networkRanges={networkRanges}
        networkRangeLabels={networkRangeLabels}
        scanStatus={scanStatus}
        scanVisibility={scanVisibility}
        timeZone={timeZone}
        onOpenScanDetails={onOpenScanDetails}
        speedtestTrackerPayload={speedtestTrackerPayload}
      />

      <DashboardInsightCards
        events={events}
        devices={devices}
        onSelectDevice={onSelectDevice}
        onOpenAttentionDevices={onOpenAttentionDevices}
        onOpenRecentChanges={onOpenRecentChanges}
        onError={onError}
        timeZone={timeZone}
      />
    </>
  );
}
