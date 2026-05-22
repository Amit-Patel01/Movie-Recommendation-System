import { RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";

export default function AdminPanel({ notify }) {
  const [users, setUsers] = useState([]);

  async function loadUsers() {
    try {
      const payload = await api.adminUsers();
      setUsers(payload.users || []);
    } catch (error) {
      notify(error.message, "error");
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function toggleRole(user) {
    try {
      await api.updateUser(user.userId, { role: user.role === "admin" ? "user" : "admin" });
      await loadUsers();
      notify("User role updated.");
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function deleteUser(user) {
    try {
      await api.deleteUser(user.userId);
      await loadUsers();
      notify("User deleted.");
    } catch (error) {
      notify(error.message, "error");
    }
  }

  return (
    <section className="section-stack">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Admin panel</p>
          <h1>User Management</h1>
        </div>
        <button onClick={loadUsers} title="Refresh users">
          <RefreshCw size={16} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>User ID</th>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.userId}>
                <td>{user.userId}</td>
                <td>{user.name}</td>
                <td>{user.email}</td>
                <td>
                  <span className={user.role === "admin" ? "role admin" : "role"}>{user.role}</span>
                </td>
                <td>
                  <div className="table-actions">
                    <button className="secondary" onClick={() => toggleRole(user)}>
                      <ShieldCheck size={15} />
                      <span>Role</span>
                    </button>
                    <button className="danger" onClick={() => deleteUser(user)}>
                      <Trash2 size={15} />
                      <span>Delete</span>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
