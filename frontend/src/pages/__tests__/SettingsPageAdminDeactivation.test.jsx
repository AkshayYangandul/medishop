/**
 * MediShop SettingsPage — admin deactivation UI tests
 * ====================================================
 *
 * Environment note: this project has no DOM test runner (no vitest/jsdom) and
 * no network is available to install one. These tests therefore render the real
 * ``SettingsPage`` to static markup with React's server renderer
 * (``renderToStaticMarkup``) and assert on the resulting HTML.
 *
 * The real data-loading effect never runs during server-side rendering, so
 * ``SettingsPage`` accepts an optional ``initialUsers`` prop (a test seam) that
 * pre-seeds the accounts table. Production behaviour is unchanged: when the prop
 * is omitted the effect loads live data on mount.
 *
 * Run:
 *   node node_modules\esbuild\bin\esbuild src\pages\__tests__\SettingsPageAdminDeactivation.test.jsx --bundle --platform=node --format=cjs --outfile .test-run/SettingsPageAdminDeactivation.bundle.cjs
 *   node .test-run\SettingsPageAdminDeactivation.bundle.cjs
 *
 * Run from the ``frontend`` directory.
 */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { assert } from 'node:assert';
import { SettingsPage } from '../SettingsPage';
import { AuthContext } from '../../context/AuthContext';

function TestAuthProvider({ user, children }) {
  const value = React.useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isInitializing: false,
      login: () => {},
      logout: () => {},
    }),
    [user]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

const currentAdmin = {
  id: 'admin-1',
  email: 'admin@medishop.com',
  role: 'admin',
  is_active: true,
};

const adminAccount = {
  id: 'user-admin-1',
  email: 'admin@medishop.com',
  full_name: 'Admin User',
  role: 'admin',
  phone: '—',
  is_active: true,
  account_locked: false,
};

const inactiveAdminAccount = {
  id: 'user-admin-2',
  email: 'admin2@medishop.com',
  full_name: 'Inactive Admin',
  role: 'admin',
  phone: '—',
  is_active: false,
  account_locked: false,
};

const pharmacistAccount = {
  id: 'user-pharm-1',
  email: 'pharm@medishop.com',
  full_name: 'Pharm User',
  role: 'pharmacist',
  phone: '—',
  is_active: true,
  account_locked: false,
};

const lockedPharmacistAccount = {
  ...pharmacistAccount,
  id: 'user-pharm-locked',
  full_name: 'Locked Pharmacist',
  email: 'locked@medishop.com',
  is_active: true,
  account_locked: 1,
};

function render(users, currentUser) {
  return renderToStaticMarkup(
    <TestAuthProvider user={currentUser}>
      <SettingsPage initialUsers={users} />
    </TestAuthProvider>
  );
}

function deactivateCount(html) {
  return (html.match(/Deactivate/g) || []).length;
}

function labelCount(html, label) {
  return (html.match(new RegExp(`>${label}</button>`, 'g')) || []).length;
}

let failures = 0;
function check(name, condition) {
  if (condition) {
    console.log(`PASS: ${name}`);
  } else {
    console.log(`FAIL: ${name}`);
    failures += 1;
  }
}

// 1. Admin viewing an active admin + an active pharmacist: only the
//    pharmacist row gets a Deactivate button.
{
  const html = render([adminAccount, pharmacistAccount], currentAdmin);
  check('Admin account row renders no Deactivate button', deactivateCount(html) === 1);
  check('Pharmacist account row renders a Deactivate button', html.includes('Deactivate'));
  check('Eligible pharmacist renders Delete', labelCount(html, 'Delete') === 1);
  check('Admin full name is rendered', html.includes('Admin User'));
  check('Pharmacist full name is rendered', html.includes('Pharm User'));
}

// 2. Admin viewing only an active admin: no Deactivate button at all.
{
  const html = render([adminAccount], currentAdmin);
  check('Only-admin list renders no Deactivate button', deactivateCount(html) === 0);
}

// 3. Admin viewing only a pharmacist: Deactivate button present.
{
  const html = render([pharmacistAccount], currentAdmin);
  check('Pharmacist-only list renders a Deactivate button', deactivateCount(html) === 1);
  check('Pharmacist-only list renders Delete', labelCount(html, 'Delete') === 1);
}

// Lock controls follow the backend account_locked value independently of active status.
{
  const html = render([lockedPharmacistAccount, pharmacistAccount], currentAdmin);
  check('Locked active pharmacist with MySQL integer lock value renders Unlock', labelCount(html, 'Unlock') === 1);
  check('Unlocked pharmacist does not add an Unlock button', labelCount(html, 'Unlock') === 1);
  check('Both active pharmacists retain Delete and Deactivate controls', labelCount(html, 'Delete') === 2 && deactivateCount(html) === 2 && !html.includes('Activate'));
}

// 4. An inactive administrator still renders an Activate button: activation
//    is not broken by the admin-deactivation restriction.
{
  const html = render([inactiveAdminAccount], currentAdmin);
  check('Inactive administrator renders an Activate button', html.includes('Activate'));
  check('Inactive administrator renders no Deactivate button', deactivateCount(html) === 0);
}

// 5. A non-admin current user cannot access the staff accounts table at all.
{
  const currentPharmacist = {
    id: 'p-1',
    email: 'pharm@medishop.com',
    role: 'pharmacist',
    is_active: true,
  };
  const html = render([adminAccount, pharmacistAccount], currentPharmacist);
  check(
    'Non-admin sees the staff-administration notice instead of the table',
    html.includes('Staff administration requires verified Active Administrator permissions')
  );
  check('Non-admin view renders no Deactivate button', deactivateCount(html) === 0);
}

if (failures > 0) {
  console.log(`\n${failures} test(s) FAILED`);
  process.exit(1);
} else {
  console.log('\nAll SettingsPage admin-deactivation UI tests PASSED');
  process.exit(0);
}
