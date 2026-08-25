import { Navigate, Route, Routes } from 'react-router'
import { SetupScreen } from './screens/Setup'
import { AnalyzeScreen } from './screens/Analyze'
import { BusinessContextScreen } from './screens/BusinessContext'
import { NewMachineScreen } from './screens/NewMachine'
import { QCModelScreen } from './screens/QCModel'
import { AnalysisResultScreen } from './screens/AnalysisResult'
import { WorkOrdersScreen } from './screens/WorkOrders'
import { WorkOrderDetailScreen } from './screens/WorkOrderDetail'
import { ExecuteScreen } from './screens/Execute'
import { ReportScreen } from './screens/Report'
import { CompareScreen } from './screens/Compare'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/analyze" replace />} />
      <Route path="/setup" element={<SetupScreen />} />
      <Route path="/machines/new" element={<NewMachineScreen />} />
      <Route path="/qc-model" element={<QCModelScreen />} />
      <Route path="/business-context" element={<BusinessContextScreen />} />
      <Route path="/analyze" element={<AnalyzeScreen />} />
      <Route path="/analysis/:id" element={<AnalysisResultScreen />} />
      <Route path="/analysis/:id/compare" element={<CompareScreen />} />
      <Route path="/work-orders" element={<WorkOrdersScreen />} />
      <Route path="/work-orders/:id" element={<WorkOrderDetailScreen />} />
      <Route path="/work-orders/:id/execute" element={<ExecuteScreen />} />
      <Route path="/work-orders/:id/report" element={<ReportScreen />} />
      <Route path="*" element={<Navigate to="/analyze" replace />} />
    </Routes>
  )
}
