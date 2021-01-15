import React, { useState } from 'react'
const apiHost = process.env.REACT_APP_API_HOST

export default function App() {
  const [now, setNow] = useState()

  async function onClick() {
    const res = await fetch(`${apiHost}/now`)
    const json = await res.json()
    setNow(json)
  }

  return <div>
    <button onClick={onClick}>Present</button>
    {now && <p>{now}</p>}
  </div>
}
