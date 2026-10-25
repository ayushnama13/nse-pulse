import { VerdictBar } from '@/components/home/VerdictBar'
import { BattleMap } from '@/components/home/BattleMap'
import { FlowMini } from '@/components/home/FlowMini'
import { ChangeFeed } from '@/components/home/ChangeFeed'
import { ContextRail } from '@/components/home/ContextRail'

/**
 * HOME — the command center. Reading order = decision order:
 * Verdict (A) → Battle Map + Session Flow (B/C, left) → What Changed +
 * Context (D/E, right rail). Every widget is a door into its full tab.
 */
export function HomeTab() {
  return (
    <div>
      <VerdictBar />
      <div className="home-grid">
        <div className="home-col">
          <BattleMap />
          <FlowMini />
        </div>
        <div className="home-col">
          <ChangeFeed />
          <ContextRail />
        </div>
      </div>
    </div>
  )
}
