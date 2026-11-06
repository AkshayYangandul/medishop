import React, { useCallback, useEffect, useState } from 'react';
import {
  Users,
  Store,
  Plus,
  RefreshCw,
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lock,
  Send,
  Trash2,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import {
  getUsers,
  createUser,
  restoreUserAccount,
  updateUserRole,
  updateUserStatus,
  unlockUserAccount,
  deleteUser,
  sendTestEmail,
  getEmailSettings,
  addEmailSender,
  updateEmailSender,
  verifyEmailSender,
  activateEmailSender,
  disableEmailSender,
} from '../services/api';

const DEFAULT_USER_FORM = {
  full_name: '',
  email: '',
  password: '',
  role: 'pharmacist',
  phone: '',
  is_active: true,
};

export function SettingsPage({ initialUsers } = {}) {
  const { user: currentUser } = useAuth();
  const isAdmin = currentUser?.role === 'admin';

  const [activeTab, setActiveTab] = useState('staff'); // 'staff' | 'store'

  // Staff State
  const [users, setUsers] = useState(Array.isArray(initialUsers) ? initialUsers : []);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Add User Form Modal
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(DEFAULT_USER_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);

  // Role / Status Action Loading
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  // Transactional email settings state
  const [emailSettingsLoading, setEmailSettingsLoading] = useState(false);
  const [mailSuccess, setMailSuccess] = useState(null);
  const [mailError, setMailError] = useState(null);
  const [emailSettings, setEmailSettings] = useState({ provider: 'brevo', brevo_configured: false, senders: [] });
  const [senderDraft, setSenderDraft] = useState({ sender_email: '', sender_name: '', reply_to_email: '' });
  const [editingSenderId, setEditingSenderId] = useState(null);
  const [providerTestRecipient, setProviderTestRecipient] = useState('');
  const [providerTestSending, setProviderTestSending] = useState(false);

  const loadUsers = useCallback(async () => {
    if (!isAdmin) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getUsers();
      setUsers(data || []);
    } catch (err) {
      setError(err?.message || 'Failed to load staff accounts.');
    } finally {
      setIsLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const loadEmailSettings = useCallback(async () => {
    if (!isAdmin) return;
    setEmailSettingsLoading(true);
    setMailError(null);
    try {
      const providerSettings = await getEmailSettings();
      setEmailSettings(providerSettings || { provider: 'brevo', brevo_configured: false, senders: [] });
    } catch (err) {
      setMailError(err?.message || 'Failed to load Brevo settings.');
    } finally {
      setEmailSettingsLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (activeTab === 'mail') loadEmailSettings();
  }, [activeTab, loadEmailSettings]);

  const handleSendProviderTestEmail = async (e) => {
    e.preventDefault();
    const recipient = providerTestRecipient.trim();
    if (!recipient || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)) {
      setMailError('Enter a valid recipient email address.');
      return;
    }
    setProviderTestSending(true);
    setMailError(null);
    setMailSuccess(null);
    try {
      const result = await sendTestEmail(recipient);
      setMailSuccess(result?.message || 'Brevo accepted the test email request. Inbox delivery is not confirmed.');
      setProviderTestRecipient('');
    } catch (err) {
      setMailError(err?.message || `Brevo could not accept the test email for ${recipient}.`);
    } finally {
      setProviderTestSending(false);
    }
  };

  const addSenderIdentity = async (e) => {
    e.preventDefault(); setMailError(null); setMailSuccess(null);
    try {
      const result = editingSenderId
        ? await updateEmailSender(editingSenderId, senderDraft)
        : await addEmailSender(senderDraft);
      setMailSuccess(result?.message || (editingSenderId ? 'Sender identity updated.' : 'Sender identity added.'));
      setSenderDraft({ sender_email: '', sender_name: '', reply_to_email: '' });
      setEditingSenderId(null);
      await loadEmailSettings();
    } catch (err) { setMailError(err?.message || 'Could not add sender identity.'); }
  };
  const markSenderVerified = async (sender) => {
    if (!window.confirm(`Check whether Brevo reports ${sender.sender_email} as active and verified. If Brevo cannot confirm it, the sender will remain inactive.`)) return;
    try {
      const result = await verifyEmailSender(sender.id);
      setMailSuccess(result?.message || 'Sender marked verified.');
      await loadEmailSettings();
    } catch (err) {
      const message = err?.message || 'Could not update sender verification status.';
      await loadEmailSettings();
      setMailError(message);
    }
  };
  const changeSenderState = async (action, sender) => {
    try {
      const result = await action(sender.id);
      setMailSuccess(result?.message || 'Sender settings updated.');
      await loadEmailSettings();
    } catch (err) {
      const message = err?.message || 'Could not update sender settings.';
      await loadEmailSettings();
      setMailError(message);
    }
  };

  const openAddUser = () => {
    setForm(DEFAULT_USER_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const submitCreateUser = async (e) => {
    e.preventDefault();
    if (!form.full_name?.trim() || !form.email?.trim() || !form.password) {
      setFormError('Full name, email, and password are required.');
      return;
    }
    if (form.password.length < 6) {
      setFormError('Password must be at least 6 characters.');
      return;
    }

    setSaving(true);
    setFormError(null);
    setActionSuccess(null);
    try {
      await createUser({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        phone: form.phone?.trim() || null,
        is_active: !!form.is_active,
      });
      setFormOpen(false);
      setActionSuccess(`Staff account for ${form.full_name} created successfully.`);
      await loadUsers();
    } catch (err) {
      if (err?.status === 409 && String(err.message).includes('Confirm restoration')) {
        const email = form.email.trim();
        const confirmed = window.confirm(
          `A deleted account already uses ${email}. Restore the existing profile? Its original password and history will be preserved, and it will remain inactive until an administrator activates it.`
        );
        if (!confirmed) {
          setFormError('Restoration canceled. The deleted account was not changed.');
          return;
        }
        try {
          const restored = await restoreUserAccount(email);
          setFormOpen(false);
          setActionSuccess(
            `${restored.full_name} was restored as an inactive account. Activate it from the account list when access is approved.`
          );
          await loadUsers();
        } catch (restoreError) {
          setFormError(restoreError?.message || 'Failed to restore the deleted account.');
        }
      } else {
        setFormError(err?.message || 'Failed to create user account.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRoleChange = async (targetUser, newRole) => {
    if (targetUser.role === newRole) return;
    setActionLoadingId(targetUser.id);
    setError(null);
    setActionSuccess(null);
    try {
      await updateUserRole(targetUser.id, newRole);
      setActionSuccess(`Updated role for ${targetUser.full_name} to ${newRole.toUpperCase()}.`);
      await loadUsers();
    } catch (err) {
      setError(err?.message || 'Failed to update user role.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleToggleActive = async (targetUser) => {
    const nextStatus = !targetUser.is_active;
    const actionVerb = nextStatus ? 'activate' : 'deactivate';
    if (!window.confirm(`Are you sure you want to ${actionVerb} user "${targetUser.full_name}"?`)) {
      return;
    }
    setActionLoadingId(targetUser.id);
    setError(null);
    setActionSuccess(null);
    try {
      await updateUserStatus(targetUser.id, nextStatus);
      setActionSuccess(`User ${targetUser.full_name} is now ${nextStatus ? 'ACTIVE' : 'DEACTIVATED'}.`);
      await loadUsers();
    } catch (err) {
      setError(err?.message || 'Failed to update active status.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleUnlock = async (targetUser) => {
    setActionLoadingId(targetUser.id);
    setError(null);
    setActionSuccess(null);
    try {
      await unlockUserAccount(targetUser.id);
      setActionSuccess(`Account for ${targetUser.full_name} unlocked successfully.`);
      await loadUsers();
    } catch (err) {
      setError(err?.message || `Failed to unlock ${targetUser.full_name}'s account.`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    const targetUser = deleteTarget;
    setActionLoadingId(targetUser.id);
    setError(null);
    setActionSuccess(null);
    try {
      await deleteUser(targetUser.id);
      setDeleteTarget(null);
      setActionSuccess(`Account for ${targetUser.full_name} was deleted successfully.`);
      await loadUsers();
    } catch (err) {
      setError(err?.message || `Failed to delete ${targetUser.full_name}'s account.`);
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings & Administration"
        subtitle="Manage pharmacy staff roles, security permissions, and store credentials"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('staff')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'staff'
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              Staff &amp; Permissions
            </button>
            <button
              onClick={() => setActiveTab('mail')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'mail'
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              Mail Settings (Email)
            </button>
            <button
              onClick={() => setActiveTab('store')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'store'
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              Pharmacy Store Profile
            </button>
          </div>
        }
      />

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {actionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* STAFF TAB */}
      {activeTab === 'staff' && (
        <Card>
          <CardContent className="p-0">
            {/* Toolbar */}
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900 text-sm">
                  Authorized Personnel Accounts
                </h3>
                <p className="text-xs text-slate-500">
                  Protected with MySQL named lock (`medishop_admin_role_mutex`) preventing last admin demotion
                </p>
              </div>

              {isAdmin && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    icon={RefreshCw}
                    onClick={loadUsers}
                    disabled={isLoading}
                  >
                    Refresh
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={Plus}
                    iconPosition="left"
                    onClick={openAddUser}
                  >
                    Add Staff Member
                  </Button>
                </div>
              )}
            </div>

            {!isAdmin ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                <ShieldAlert className="w-8 h-8 text-amber-500 mx-auto mb-2" />
                Staff administration requires verified Active Administrator permissions.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                    <tr>
                      <th className="py-3 px-5 font-semibold">Staff Member</th>
                      <th className="py-3 px-4 font-semibold">Email</th>
                      <th className="py-3 px-4 font-semibold">Phone</th>
                      <th className="py-3 px-4 font-semibold">Assigned Role</th>
                      <th className="py-3 px-4 font-semibold text-center">Status</th>
                      <th className="py-3 px-5 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {isLoading ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400">
                          <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                          Loading staff profiles...
                        </td>
                      </tr>
                    ) : users.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400">
                          <Users className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                          No staff accounts found.
                        </td>
                      </tr>
                    ) : (
                      users.map((u) => {
                        const isCurrent = currentUser?.id === u.id;
                        const isBusy = actionLoadingId === u.id;
                        const isAccountLocked = u.account_locked === true || u.account_locked === 1;
                        return (
                          <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                            <td className="py-3.5 px-5 font-medium text-slate-900">
                              {u.full_name}
                              {isCurrent && (
                                <span className="ml-2 text-[10px] bg-brand-50 text-brand-700 px-1.5 py-0.5 rounded font-semibold">
                                  You
                                </span>
                              )}
                            </td>
                            <td className="py-3.5 px-4 text-xs font-mono text-slate-600">
                              {u.email}
                            </td>
                            <td className="py-3.5 px-4 text-xs text-slate-600">
                              {u.phone || '—'}
                            </td>
                            <td className="py-3.5 px-4">
                              <select
                                value={u.role}
                                disabled={isBusy}
                                onChange={(e) => handleRoleChange(u, e.target.value)}
                                className="px-2.5 py-1 border border-slate-200 rounded-lg text-xs font-semibold uppercase bg-white cursor-pointer focus:ring-2 focus:ring-brand-500"
                              >
                                <option value="admin">Administrator</option>
                                <option value="pharmacist">Pharmacist</option>
                              </select>
                            </td>
                            <td className="py-3.5 px-4 text-center">
                              <Badge variant={u.is_active ? 'success' : 'neutral'} size="sm">
                                {u.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                            </td>
                            <td className="py-3.5 px-5 text-right">
                              <div className="flex justify-end gap-2">
                              {u.role === 'pharmacist' && isAccountLocked && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={isBusy}
                                  onClick={() => handleUnlock(u)}
                                >
                                  {isBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Unlock'}
                                </Button>
                              )}
                              {u.role !== 'admin' && (
                                <Button
                                  variant="danger"
                                  size="sm"
                                  icon={Trash2}
                                  disabled={isBusy}
                                  onClick={() => setDeleteTarget(u)}
                                >
                                  Delete
                                </Button>
                              )}
                              {u.role === 'admin' && u.is_active ? null : (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isBusy}
                                onClick={() => handleToggleActive(u)}
                                className={u.is_active ? 'hover:text-rose-600' : 'hover:text-emerald-600'}
                              >
                                {isBusy ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : u.is_active ? (
                                  'Deactivate'
                                ) : (
                                  'Activate'
                                )}
                              </Button>
                              )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4" role="presentation">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-100" role="dialog" aria-modal="true" aria-labelledby="delete-account-title">
            <h3 id="delete-account-title" className="text-base font-bold text-slate-900 mb-2">Delete staff account?</h3>
            <p className="text-sm text-slate-700 mb-2">
              Delete <strong>{deleteTarget.full_name}</strong> ({deleteTarget.email})?
            </p>
            <p className="text-sm text-rose-700 mb-5">
              This retires the account and prevents future access. Historical business records and the staff identity attached to them are preserved.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" size="sm" disabled={actionLoadingId === deleteTarget.id} onClick={() => setDeleteTarget(null)}>
                Cancel
              </Button>
              <Button variant="danger" size="sm" disabled={actionLoadingId === deleteTarget.id} onClick={handleDelete}>
                {actionLoadingId === deleteTarget.id ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                Confirm Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* BREVO MAIL SETTINGS TAB */}
      {activeTab === 'mail' && (
        <div className="space-y-6">
          {mailError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{mailError}</span>
            </div>
          )}

          {mailSuccess && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <span>{mailSuccess}</span>
            </div>
          )}

          <Card>
            <CardContent className="p-6 space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-slate-900">Transactional Email Provider</h3>
                  <p className="text-xs text-slate-500 mt-1">Selected provider: <strong className="uppercase">{emailSettings.provider}</strong> · Brevo API key {emailSettings.brevo_configured ? 'configured' : 'not configured'}</p>
                </div>
                <Badge variant={emailSettings.provider === 'brevo' && emailSettings.brevo_configured ? 'brand' : 'slate'} size="sm">
                  {emailSettings.provider === 'brevo' ? 'Brevo selected' : 'Brevo only'}
                </Badge>
              </div>
              {emailSettings.provider === 'brevo' && (
                <p className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900">
                  Brevo is the only transactional email provider. Verify each sender in Brevo before activation; MediShop checks its current status before every activation. API acceptance does not confirm inbox delivery.
                </p>
              )}
              <form onSubmit={addSenderIdentity} className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
                <label className="text-xs font-semibold text-slate-600">Sender email<input required type="email" value={senderDraft.sender_email} onChange={e => setSenderDraft({...senderDraft, sender_email:e.target.value})} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                <label className="text-xs font-semibold text-slate-600">Display name<input required value={senderDraft.sender_name} onChange={e => setSenderDraft({...senderDraft, sender_name:e.target.value})} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                <label className="text-xs font-semibold text-slate-600">Reply-To (optional)<input type="email" value={senderDraft.reply_to_email} onChange={e => setSenderDraft({...senderDraft, reply_to_email:e.target.value})} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
                <div className="flex gap-2"><Button type="submit" variant="primary" size="md">{editingSenderId ? 'Save sender' : 'Add sender'}</Button>{editingSenderId && <Button type="button" variant="outline" size="md" onClick={() => { setEditingSenderId(null); setSenderDraft({sender_email:'',sender_name:'',reply_to_email:''}); }}>Cancel</Button>}</div>
              </form>
              <div className="space-y-2">
                {emailSettings.senders?.length ? emailSettings.senders.map(sender => (
                  <div key={sender.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3">
                    <div><div className="text-sm font-semibold text-slate-800">{sender.sender_name} &lt;{sender.sender_email}&gt;</div><div className="text-xs text-slate-500">{sender.reply_to_email ? `Reply-To: ${sender.reply_to_email} · ` : ''}{sender.is_verified && sender.verification_method === 'brevo_api' ? 'Brevo API verified' : 'Unverified'}{sender.is_active ? ' · Active' : ''}{sender.disabled_at ? ' · Disabled' : ''}</div></div>
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="outline" size="sm" onClick={() => { setEditingSenderId(sender.id); setSenderDraft({sender_email:sender.sender_email,sender_name:sender.sender_name,reply_to_email:sender.reply_to_email || ''}); }}>Edit</Button>
                      {(sender.disabled_at || !sender.is_verified || !sender.is_active) && <Button type="button" variant="outline" size="sm" onClick={() => markSenderVerified(sender)}>Check Brevo verification</Button>}
                      {sender.is_verified && !sender.is_active && <Button type="button" variant="outline" size="sm" onClick={() => changeSenderState(activateEmailSender, sender)}>{sender.disabled_at ? 'Enable' : 'Set active'}</Button>}
                      {!sender.disabled_at && <Button type="button" variant="outline" size="sm" onClick={() => changeSenderState(disableEmailSender, sender)}>Disable</Button>}
                    </div>
                  </div>
                )) : <p className="text-sm text-slate-500">No sender identities configured.</p>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-start gap-3 mb-4">
                <div className="p-2.5 bg-brand-50 text-brand-600 rounded-xl"><Send className="w-5 h-5" /></div>
                <div>
                  <h3 className="font-semibold text-slate-900">Send Test Email</h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Sends through Brevo using the currently active verified sender identity.
                    Provider acceptance does not confirm inbox delivery.
                  </p>
                </div>
              </div>
              <form onSubmit={handleSendProviderTestEmail} className="flex flex-col sm:flex-row gap-3 sm:items-end">
                <label className="flex-1 text-xs font-semibold text-slate-700">
                  Recipient email
                  <input
                    type="email"
                    required
                    value={providerTestRecipient}
                    onChange={(event) => setProviderTestRecipient(event.target.value)}
                    placeholder="admin@example.com"
                    className="mt-1 w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  />
                </label>
                <Button type="submit" variant="primary" size="md" disabled={providerTestSending || emailSettingsLoading} icon={providerTestSending ? Loader2 : Send}>
                  {providerTestSending ? 'Sending test…' : 'Send Test Email'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button type="button" variant="outline" size="sm" onClick={loadEmailSettings}
              disabled={emailSettingsLoading} icon={RefreshCw}>
              Refresh sender settings
            </Button>
          </div>
        </div>
      )}

      {/* STORE PROFILE TAB */}
      {activeTab === 'store' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-6 space-y-5">
                <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
                  <div className="p-3 bg-brand-50 text-brand-600 rounded-xl">
                    <Store className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900 text-base">
                      MediShop Pharmacy &amp; Retail Healthcare
                    </h3>
                    <p className="text-xs text-slate-400">
                      Standard store profile &amp; regulatory licenses
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                  <div>
                    <label className="text-xs font-semibold text-slate-500">Retail Drug License (Form 20/21)</label>
                    <div className="font-mono font-medium text-slate-800 mt-1">MH-SZ4-490218</div>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-500">GSTIN Registration</label>
                    <div className="font-mono font-medium text-slate-800 mt-1">27AAAPM1234F1Z8</div>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-500">Store Contact Number</label>
                    <div className="text-slate-800 mt-1">+91 (022) 2890-4411</div>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-500">Support / Prescription Email</label>
                    <div className="text-slate-800 mt-1">contact@medishop-rx.com</div>
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-xs font-semibold text-slate-500">Store Registered Address</label>
                    <div className="text-slate-800 mt-1">
                      Shop #4, Ground Floor, Sai Plaza, Station Road, Mumbai, MH - 400092
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div>
            <Card>
              <CardContent className="p-6 space-y-4">
                <h4 className="font-semibold text-slate-900 text-sm flex items-center gap-2">
                  <Lock className="w-4 h-4 text-emerald-600" />
                  System Security Architecture
                </h4>
                <div className="space-y-3 text-xs text-slate-600">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>FastAPI Backend + MySQL 8 Enterprise Engine</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>Cryptographic HS256 JWT Bearer Authentication</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>PBKDF2-HMAC-SHA256 (260k iterations) Password Salted Hashing</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>MySQL Named Lock Mutex Concurrency Protection</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>Immutable Audit Trails &amp; Strict Stock Movement Triggers</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Add User Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-base">Create Staff Profile</h3>
              <button onClick={() => setFormOpen(false)} className="text-slate-400 hover:text-slate-600 text-lg">
                &times;
              </button>
            </div>

            <form onSubmit={submitCreateUser} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Priya Sharma"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email Address *
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="priya@medishop.com"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Initial Password *
                  </label>
                  <input
                    type="password"
                    required
                    minLength={6}
                    placeholder="Min 6 characters"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    System Role *
                  </label>
                  <select
                    value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white"
                  >
                    <option value="pharmacist">Pharmacist (POS, Medicines &amp; Patients)</option>
                    <option value="admin">Administrator (Full Access)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    placeholder="+91 98765 43210"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex justify-end gap-3">
                <Button variant="outline" size="sm" type="button" onClick={() => setFormOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={saving}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5 inline" />
                  ) : null}
                  Create Account
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
