import { Modal, Table } from 'antd'

const SHORTCUTS = [
  { combo: '1 – 7', action: 'Jump to a top-bar section' },
  { combo: 'S', action: 'Force a snapshot' },
  { combo: 'Ctrl / ⌘ + K', action: 'Open the command palette' },
  { combo: '?', action: 'Show this shortcuts panel' },
  { combo: 'Click strike', action: 'Pin / unpin a strike (highlighted everywhere)' },
]

export function ShortcutsHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onCancel={onClose} footer={null} title="Keyboard shortcuts" width={460}>
      <Table
        size="small"
        pagination={false}
        showHeader={false}
        rowKey="combo"
        dataSource={SHORTCUTS}
        columns={[
          { dataIndex: 'combo', width: 130, render: (k: string) => <kbd style={{ fontFamily: 'IBM Plex Mono', fontSize: 12 }}>{k}</kbd> },
          { dataIndex: 'action' },
        ]}
      />
    </Modal>
  )
}
