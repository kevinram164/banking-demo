import React, { useEffect, useMemo, useState } from "react";
import { api, getSession } from "./api";

export default function Dashboard({ onLogout }) {
  const [me, setMe] = useState(null);
  const [toUser, setToUser] = useState("");
  const [amount, setAmount] = useState(1000);
  const [noti, setNoti] = useState([]);

  const session = getSession();
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${scheme}://${window.location.host}/ws?session=${encodeURIComponent(session)}`;
  
  const ws = new WebSocket(wsUrl);

  const refresh = async () => {
    const m = await api.me();
    setMe(m);
    const ns = await api.notifications();
    setNoti(ns);
  };

  useEffect(() => {
    refresh().catch(()=>{});
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      // keep alive ping
      setInterval(() => {
        try { ws.send("ping"); } catch {}
      }, 15000);
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "notification") {
          setNoti(prev => [{ id: "rt-"+Date.now(), message: data.message }, ...prev]);
        }
      } catch {}
    };
    return () => ws.close();
  }, [wsUrl]);

  const doTransfer = async () => {
    await api.transfer(toUser, amount);
    await refresh();
  };

  if (!me) return <div>Loading...</div>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ border:"1px solid #ddd", padding:16, borderRadius:12 }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <div>
            <b>User:</b> {me.username} <br/>
            <b>Balance:</b> {me.balance}
          </div>
          <button onClick={onLogout}>Logout</button>
        </div>
      </div>

      <div style={{ border:"1px solid #ddd", padding:16, borderRadius:12 }}>
        <h3>Transfer</h3>
        <input placeholder="to username" value={toUser} onChange={e=>setToUser(e.target.value)} />
        <span style={{ marginLeft: 8 }} />
        <input style={{ width: 120 }} type="number" value={amount} onChange={e=>setAmount(e.target.value)} />
        <button style={{ marginLeft: 8 }} onClick={doTransfer}>Send</button>
      </div>

      <div style={{ border:"1px solid #ddd", padding:16, borderRadius:12 }}>
        <h3>Notifications</h3>
        <ul>
          {noti.slice(0, 20).map((x, idx) => (
            <li key={x.id ?? idx}>{x.message}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
