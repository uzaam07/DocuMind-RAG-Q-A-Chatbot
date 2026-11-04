import { useId, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowUpRight, Check, Eye, EyeOff, FileText, LockKeyhole, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-react';
import { api } from '../api/client.js';
import { useAuth } from '../state/auth.jsx';
import { useTitle } from '../state/useTitle.js';
import Wordmark from '../components/Wordmark.jsx';
import SegmentedControl from '../components/SegmentedControl.jsx';
import ThemeToggle from '../components/ThemeToggle.jsx';

const EMAIL_PATTERN = /^\S+@\S+\.\S+$/;
const ACTIONS = [
  { value: 'signin', label: 'Sign in' },
  { value: 'register', label: 'Create account' },
];

function safeNext(raw) {
  return raw && raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/login') ? raw : '/chat';
}

function validate(action, email, password) {
  const errors = {};
  if (!email.trim()) errors.email = 'Enter your email address.';
  else if (!EMAIL_PATTERN.test(email.trim())) errors.email = 'Enter an email address like name@example.com.';
  if (!password) errors.password = 'Enter your password.';
  else if (action === 'register' && password.length < 8) errors.password = 'Use at least 8 characters for the password.';
  return errors;
}

function FieldError({ id, children }) {
  if (!children) return null;
  return (
    <p id={id} className="field-error">
      <TriangleAlert size={16} strokeWidth={1.5} aria-hidden="true" />
      {children}
    </p>
  );
}

export default function Login() {
  useTitle('Sign in');
  const { token, signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const [action, setAction] = useState('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [reveal, setReveal] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null);
  const ids = { email: useId(), password: useId(), emailErr: useId(), passErr: useId(), formErr: useId() };

  if (token) return <Navigate to={next} replace />;

  const errors = submitted ? validate(action, email, password) : {};
  const register = action === 'register';
  const passwordScore = [password.length >= 8, /[A-Z]/.test(password), /[0-9]/.test(password), /[^A-Za-z0-9]/.test(password)].filter(Boolean).length;
  const passwordLabel = ['Add a password to check its strength', 'Needs improvement', 'Fair strength', 'Good strength', 'Strong password'][passwordScore];

  const onSubmit = async (event) => {
    event.preventDefault();
    setSubmitted(true);
    setFormError(null);
    if (Object.keys(validate(action, email, password)).length > 0) return;
    setBusy(true);
    try {
      const call = register ? api.register : api.login;
      const response = await call(email.trim(), password);
      signIn(response);
      navigate(next, { replace: true });
    } catch (err) {
      setFormError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="login login--split">
      <header className="login__top">
        <Wordmark />
        <div className="login__top-actions">
          <span className="login__secure"><ShieldCheck size={14} /> Secure workspace</span>
          <ThemeToggle />
        </div>
      </header>
      <main className="login__layout">
        <section className="login__story" aria-label="About DocuMind">
          <div className="login__story-inner">
            <div className="login__eyebrow"><span className="login__eyebrow-dot" /> DOCUMENT INTELLIGENCE, REFINED</div>
            <h1>Make every document<br /><span>work smarter.</span></h1>
            <p className="login__purpose">A focused workspace for asking better questions, tracing every answer to its source, and moving from information to insight.</p>
            <div className="login__preview" aria-label="Product capabilities">
              <div className="login__preview-head"><span><span className="login__live-dot" /> WORKSPACE PREVIEW</span><span className="mono">DM / 01</span></div>
              <div className="login__preview-query"><span className="login__query-icon"><Sparkles size={15}/></span><span>What are the key renewal terms?</span><ArrowUpRight size={15}/></div>
              <div className="login__preview-answer">
                <div className="login__answer-label">ANSWER OVERVIEW <span>3 SOURCES</span></div>
                <div className="login__answer-line login__answer-line--wide" />
                <div className="login__answer-line" />
                <div className="login__answer-line login__answer-line--short" />
                <div className="login__source"><FileText size={14}/><span>Service_Agreement.pdf</span><span className="login__source-page">PAGE 08</span><Check size={14}/></div>
              </div>
            </div>
            <div className="login__principles">
              <div><LockKeyhole size={15}/><span>Private by design</span></div>
              <div><ShieldCheck size={15}/><span>Evidence-led answers</span></div>
            </div>
          </div>
          <div className="login__story-foot"><span>BUILT FOR CLARITY.</span><span>01 — 03</span></div>
        </section>

        <section className="login__panel" aria-labelledby="auth-title">
          <div className="login__form-wrap">
            <div className="login__mobile-brand"><Wordmark /></div>
            <div className="login__form-heading">
              <span className="login__kicker">YOUR WORKSPACE AWAITS</span>
              <h2 id="auth-title">{register ? 'Create your account' : 'Welcome back'}</h2>
              <p>{register ? 'Set up your DocuMind workspace in a moment.' : 'Sign in to continue where your thinking left off.'}</p>
            </div>
            <SegmentedControl
              label="Account action"
              options={ACTIONS}
              value={action}
              onChange={(value) => { setAction(value); setFormError(null); setSubmitted(false); }}
            />
            <form className="form login__form" onSubmit={onSubmit} noValidate aria-describedby={formError ? ids.formErr : undefined}>
              <div className="field">
                <label htmlFor={ids.email}>Email address</label>
                <input id={ids.email} className="input" type="email" placeholder="you@company.com" autoComplete="email" inputMode="email" value={email} aria-invalid={errors.email ? true : undefined} aria-describedby={errors.email ? ids.emailErr : undefined} onChange={(event) => setEmail(event.target.value)} />
                <FieldError id={ids.emailErr}>{errors.email}</FieldError>
              </div>
              <div className="field">
                <div className="login__label-row"><label htmlFor={ids.password}>Password</label>{!register ? <span className="login__field-meta">SECURE ACCESS</span> : null}</div>
                <div className="input-group">
                  <input id={ids.password} className="input" placeholder={register ? 'Create a strong password' : 'Enter your password'} type={reveal ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} value={password} aria-invalid={errors.password ? true : undefined} aria-describedby={errors.password ? ids.passErr : undefined} onChange={(event) => setPassword(event.target.value)} />
                  <button type="button" className="icon-btn" aria-label={reveal ? 'Hide password' : 'Show password'} aria-pressed={reveal} onClick={() => setReveal((v) => !v)}>{reveal ? <EyeOff size={17} /> : <Eye size={17} />}</button>
                </div>
                {register ? <div className="password-strength" aria-live="polite"><div className="password-strength__bars">{[1,2,3,4].map((n) => <span key={n} data-active={passwordScore >= n || undefined} />)}</div><span>{passwordLabel}</span></div> : null}
                <FieldError id={ids.passErr}>{errors.password}</FieldError>
              </div>
              {formError ? <div id={ids.formErr} className="form-error" role="alert"><TriangleAlert size={16} /><p>{formError}</p></div> : null}
              <button type="submit" className="btn btn--primary btn--lg login__submit" disabled={busy}>
                {busy ? (register ? 'Creating account…' : 'Signing in…') : register ? 'Create account' : 'Sign in'}<ArrowUpRight size={17}/>
              </button>
            </form>
            <div className="login__trust"><ShieldCheck size={15}/><span>Your documents stay within your private workspace.</span></div>
            <div className="login__onboarding"><span className="login__onboarding-icon"><Sparkles size={15}/></span><span><strong>New to DocuMind?</strong> Start by uploading a document, then ask a question in plain language.</span></div>
          </div>
          <footer className="login__panel-foot"><span>© {new Date().getFullYear()} DOCUMIND</span><span>THOUGHTFUL SOFTWARE. TRACEABLE ANSWERS.</span></footer>
        </section>
      </main>
    </div>
  );
}
