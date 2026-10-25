import { useState } from 'react'
import { Tag, Button, Select, Input, Space, Popover } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useShell } from '@/store'
import { useNotes, useAddNote, useDeleteNote } from '@/api/queries'

/** Strike-level notes chips above the chain table (legacy parity).
 *  Chip = "22500 CE: watch wall" with close-to-delete; popover form to add. */
export function NotesStrip() {
  const symbol = useShell((s) => s.symbol)
  const snap = useShell((s) => s.snap)
  const { data } = useNotes(symbol)
  const add = useAddNote(symbol)
  const del = useDeleteNote(symbol)

  const [open, setOpen] = useState(false)
  const [strike, setStrike] = useState<number | undefined>()
  const [side, setSide] = useState<'CE' | 'PE' | undefined>()
  const [body, setBody] = useState('')

  const strikes = (snap?.chain ?? []).map((r) => r.strike)
  const notes = data?.notes ?? []

  const submit = () => {
    if (strike == null || !body.trim()) return
    add.mutate(
      { strike, body: body.trim(), side: side ?? null },
      {
        onSuccess: () => {
          setBody('')
          setOpen(false)
        },
      },
    )
  }

  const form = (
    <Space direction="vertical" style={{ width: 240 }}>
      <Select
        size="small"
        placeholder="Strike"
        value={strike}
        onChange={setStrike}
        options={strikes.map((s) => ({ value: s, label: String(s) }))}
        style={{ width: '100%' }}
        showSearch
      />
      <Select
        size="small"
        placeholder="Side (optional)"
        value={side}
        onChange={setSide}
        allowClear
        options={[
          { value: 'CE', label: 'CE' },
          { value: 'PE', label: 'PE' },
        ]}
        style={{ width: '100%' }}
      />
      <Input.TextArea
        rows={2}
        placeholder="Note…"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onPressEnter={(e) => {
          e.preventDefault()
          submit()
        }}
      />
      <Button size="small" type="primary" block loading={add.isPending} onClick={submit} disabled={strike == null || !body.trim()}>
        Add note
      </Button>
    </Space>
  )

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginBottom: 8 }}>
      {notes.map((n) => (
        <Tag
          key={n.id}
          closable
          onClose={(e) => {
            e.preventDefault()
            del.mutate(n.id)
          }}
          color="gold"
        >
          <span className="mono">
            {n.strike}
            {n.side ? ` ${n.side}` : ''}
          </span>
          : {n.body}
        </Tag>
      ))}
      <Popover content={form} title="New strike note" trigger="click" open={open} onOpenChange={setOpen}>
        <Button size="small" type="dashed" icon={<PlusOutlined />}>
          Note
        </Button>
      </Popover>
    </div>
  )
}
