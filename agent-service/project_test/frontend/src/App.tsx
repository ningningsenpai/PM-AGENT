import { FormEvent, useEffect, useMemo, useState } from 'react'
import { createStudent, listStudents } from './api'
import type { CreateStudentRequest, Student } from './types'

const emptyForm: CreateStudentRequest = {
  studentNo: '',
  name: '',
  gender: 'FEMALE',
  grade: '2026级',
  phone: '',
  email: '',
}

export default function App() {
  const [students, setStudents] = useState<Student[]>([])
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Student | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<CreateStudentRequest>(emptyForm)
  const [saving, setSaving] = useState(false)

  const activeCount = useMemo(() => students.filter((item) => item.status === 'ACTIVE').length, [students])

  async function loadStudents(name = '') {
    setLoading(true)
    setError('')
    try {
      setStudents(await listStudents(name))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '学生档案加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadStudents()
  }, [])

  function handleSearch(event: FormEvent) {
    event.preventDefault()
    void loadStudents(keyword.trim())
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const student = await createStudent(form)
      setShowForm(false)
      setForm(emptyForm)
      setSelected(student)
      await loadStudents(keyword.trim())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '学生档案保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="shell">
      <header className="masthead">
        <div className="brand-mark">青</div>
        <div>
          <p className="eyebrow">QINGHE ACADEMIC OFFICE · 2026</p>
          <h1>青禾学籍册</h1>
          <p className="subtitle">让每一份学生档案，清楚、安静地留在案头。</p>
        </div>
        <button className="primary-button" onClick={() => setShowForm(true)}>＋ 录入学生</button>
      </header>

      <section className="summary-grid">
        <article className="summary-card featured">
          <span>当前档案</span><strong>{students.length}</strong><small>份已载入名册</small>
        </article>
        <article className="summary-card">
          <span>在读学生</span><strong>{activeCount}</strong><small>状态正常</small>
        </article>
        <article className="summary-card note-card">
          <span>开发札记</span><strong>50%</strong><small>基础档案阶段已联通</small>
        </article>
      </section>

      <section className="ledger">
        <div className="ledger-heading">
          <div><p className="section-index">01 / 学生档案</p><h2>在册学生</h2></div>
          <form className="search" onSubmit={handleSearch}>
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="输入姓名检索…" />
            <button type="submit">查找</button>
          </form>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {loading ? <div className="empty-state">正在翻阅档案…</div> : students.length === 0 ? (
          <div className="empty-state">没有找到相符的学生档案。</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>学号</th><th>姓名</th><th>年级</th><th>联系方式</th><th>状态</th><th></th></tr></thead>
              <tbody>
                {students.map((student) => (
                  <tr key={student.id} onClick={() => setSelected(student)}>
                    <td className="mono">{student.studentNo}</td>
                    <td><span className="avatar">{student.name.slice(0, 1)}</span><b>{student.name}</b></td>
                    <td>{student.grade}</td>
                    <td><span>{student.phone || '—'}</span><small>{student.email || '未登记邮箱'}</small></td>
                    <td><span className={`status ${student.status.toLowerCase()}`}>{student.status === 'ACTIVE' ? '在读' : '停用'}</span></td>
                    <td className="arrow">→</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer><span>青禾教务处 · 内部试运行名册</span><span>阶段一 / 基础档案</span></footer>

      {selected && (
        <div className="overlay" onClick={() => setSelected(null)}>
          <aside className="drawer" onClick={(event) => event.stopPropagation()}>
            <button className="close" onClick={() => setSelected(null)}>×</button>
            <p className="section-index">学生档案 / #{selected.id}</p>
            <div className="portrait">{selected.name.slice(0, 1)}</div>
            <h2>{selected.name}</h2><p className="student-number">学号 {selected.studentNo}</p>
            <dl><div><dt>年级</dt><dd>{selected.grade}</dd></div><div><dt>性别</dt><dd>{selected.gender === 'FEMALE' ? '女' : '男'}</dd></div><div><dt>电话</dt><dd>{selected.phone || '未登记'}</dd></div><div><dt>邮箱</dt><dd>{selected.email || '未登记'}</dd></div></dl>
            <div className="pending-tip">编辑与成绩档案将在阶段二开放</div>
          </aside>
        </div>
      )}

      {showForm && (
        <div className="overlay" onClick={() => setShowForm(false)}>
          <form className="drawer form-drawer" onSubmit={handleCreate} onClick={(event) => event.stopPropagation()}>
            <button type="button" className="close" onClick={() => setShowForm(false)}>×</button>
            <p className="section-index">新建档案</p><h2>录入学生</h2>
            <label>学号<input required minLength={4} value={form.studentNo} onChange={(event) => setForm({ ...form, studentNo: event.target.value })} /></label>
            <label>姓名<input required minLength={2} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <div className="field-row"><label>性别<select value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value as 'MALE' | 'FEMALE' })}><option value="FEMALE">女</option><option value="MALE">男</option></select></label><label>年级<input required value={form.grade} onChange={(event) => setForm({ ...form, grade: event.target.value })} /></label></div>
            <label>联系电话<input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
            <label>邮箱<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
            <button className="primary-button full" disabled={saving}>{saving ? '正在归档…' : '确认录入'}</button>
          </form>
        </div>
      )}
    </main>
  )
}

