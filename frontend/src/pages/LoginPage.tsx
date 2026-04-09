import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { post } from '../api/client';
import { useStore } from '../store/useStore';
import NyxLogo from '../components/NyxLogo';

export default function LoginPage() {
  const navigate = useNavigate();
  const setUser = useStore((s: { setUser: (u: { email: string; role: string; token: string }) => void }) => s.setUser);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!email.trim()) { setError('Email is required'); return; }
    if (!password.trim()) { setError('Password is required'); return; }

    setLoading(true);
    try {
      const res = await post<{ access_token: string; user?: { role?: string }; role?: string }>('/../auth/login', { email, password });
      if (res.access_token) {
        localStorage.setItem('token', res.access_token);
        setUser({ email, role: res.user?.role || res.role || 'admin', token: res.access_token });
        navigate('/');
      } else {
        setError('Invalid credentials');
      }
    } catch {
      setError('Connection failed. Please check if the server is running.');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--bg3)', border: '1px solid var(--b1)',
    borderRadius: 8, padding: '10px 14px', color: '#fff', fontSize: 13,
    outline: 'none', transition: 'border-color 0.15s',
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg0)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      {/* Background ambience */}
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 30% 20%, rgba(0,229,255,.04) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(0,200,255,.03) 0%, transparent 50%)' }} />

      <div style={{ position: 'relative', width: '100%', maxWidth: 420 }}>
        {/* ── Brand Header ── */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <NyxLogo size={110} />
          </div>

          <h1 style={{ fontSize: 34, fontWeight: 800, color: '#fff', marginTop: 18, letterSpacing: -0.5 }}>
            NYX <span style={{ color: 'var(--sky)' }}>Core</span>
          </h1>

          <p style={{
            color: 'var(--sky)', fontSize: 11, fontWeight: 600,
            letterSpacing: 3.5, textTransform: 'uppercase', marginTop: 6, opacity: 0.9,
          }}>
            System of Intelligence
          </p>

          <p style={{
            color: 'var(--muted)', fontSize: 12, lineHeight: 1.7,
            maxWidth: 360, margin: '14px auto 0', opacity: 0.7,
          }}>
            We help companies instantly detect and explain financial problems across business units
          </p>
        </div>

        {/* ── Login Card ── */}
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 12, padding: 28 }}>
          <h2 style={{ fontSize: 17, fontWeight: 600, color: '#fff', marginBottom: 2 }}>Welcome back</h2>
          <p style={{ color: 'var(--muted)', fontSize: 12, marginBottom: 20 }}>Sign in to your intelligence dashboard</p>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {error && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--rose)', fontSize: 12, background: 'rgba(248,113,113,.08)', border: '1px solid rgba(248,113,113,.15)', borderRadius: 8, padding: '8px 12px' }}>
                <AlertCircle size={14} /> {error}
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} style={inputStyle}
                placeholder="you@company.com" autoComplete="email"
                onFocus={e => e.currentTarget.style.borderColor = 'var(--sky)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,.05)'} />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Password</label>
              <div style={{ position: 'relative' }}>
                <input type={showPassword ? 'text' : 'password'} value={password}
                  onChange={e => setPassword(e.target.value)} style={{ ...inputStyle, paddingRight: 36 }}
                  placeholder="Enter password" autoComplete="current-password"
                  onFocus={e => e.currentTarget.style.borderColor = 'var(--sky)'}
                  onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,.05)'} />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer' }}>
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)}
                  style={{ accentColor: 'var(--sky)' }} />
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>Remember me</span>
              </label>
              <button type="button" style={{ fontSize: 11, color: 'var(--sky)', background: 'none', border: 'none', cursor: 'pointer' }}>Forgot password?</button>
            </div>

            <button type="submit" disabled={loading} style={{
              width: '100%', background: 'linear-gradient(135deg, var(--sky), var(--blue))',
              color: '#fff', fontWeight: 600, padding: '10px 0', borderRadius: 8, border: 'none',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              fontSize: 13, opacity: loading ? 0.6 : 1,
            }}>
              {loading ? (
                <div style={{ width: 18, height: 18, border: '2px solid rgba(0,0,0,.3)', borderTopColor: '#000', borderRadius: '50%', animation: 'spin 0.6s linear infinite' }} />
              ) : (
                <><LogIn size={16} /> Sign In</>
              )}
            </button>
          </form>
        </div>

        <p style={{ textAlign: 'center', color: 'var(--dim)', fontSize: 10, marginTop: 20, fontFamily: 'var(--mono)' }}>
          Powered by NYX Core Intelligence Engine
        </p>
      </div>
    </div>
  );
}
