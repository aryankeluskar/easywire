async function initClerk() {
  try {
    if (!window.Clerk) {
      console.error('Clerk not loaded yet');
      return;
    }
    
    await window.Clerk.load();

    // Add event listeners for auth state changes
    window.Clerk.addListener(({ user }) => {
      const signOutContainer = document.getElementById('sign-out-container');
      const emailInput = document.getElementById('email');
      if (signOutContainer) {
        if (user) {
          signOutContainer.innerHTML = `
            <div class="auth-container" style="display: inline-flex; align-items: center; gap: 0.25rem;">
              <button class="cpvyo cv7b2 cj90m cgvn6 c2gcs ccjiw cjnro c02c5" id="profile-button" style="padding: 0.4rem 0.6rem; font-size: 0.875rem; white-space: nowrap;">
                ${user.firstName}
              </button>
              <button class="cpvyo cv7b2 cj90m cgvn6 c2gcs ccjiw cjnro c02c5" id="sign-out-button" style="padding: 0.4rem 0.6rem; font-size: 0.875rem; white-space: nowrap;">
                Log Out
              </button>
            </div>
          `;
          // Pre-fill and disable email input if user is logged in
          if (emailInput) {
            emailInput.value = user.primaryEmailAddress.emailAddress;
            emailInput.setAttribute('readonly', 'readonly');
          }
          document.getElementById('profile-button').onclick = () => window.Clerk.openUserProfile();
          document.getElementById('sign-out-button').onclick = async () => {
            await window.Clerk.signOut();
            document.getElementById('user-greeting').style.display = 'none';
            document.getElementById('alerts-link').style.display = 'none';
            document.getElementById('github-link').style.display = 'block';
            document.getElementById('perplexity-link').style.display = 'block';
            document.getElementById('contact-link').style.display = 'block';
            window.location.href = '/';
          };
          // Show/hide elements based on authentication
          document.getElementById('user-greeting').style.display = 'block';
          document.getElementById('user-greeting').querySelector('span').textContent = `Home`;
          document.getElementById('user-greeting').onclick = () => window.location.href = '/';
          document.getElementById('alerts-link').style.display = 'block';
          document.getElementById('github-link').style.display = 'none';
          document.getElementById('perplexity-link').style.display = 'none';
        } else {
          signOutContainer.innerHTML = `
            <button class="cpvyo cv7b2 cj90m cgvn6 c2gcs ccjiw cjnro c02c5" id="sign-in-button" style="padding: 0.4rem 0.6rem; font-size: 0.875rem; white-space: nowrap;">Sign In</button>
          `;
          document.getElementById('sign-in-button').onclick = () => window.Clerk.openSignIn();
          // Show/hide elements based on authentication
          document.getElementById('user-greeting').style.display = 'none';
          document.getElementById('alerts-link').style.display = 'none';
          document.getElementById('github-link').style.display = 'block';
          document.getElementById('perplexity-link').style.display = 'block';
        }
      }
    });

  } catch (err) {
    console.error('Error initializing Clerk:', err);
  }
}

// Wait for Clerk to be available
function waitForClerk() {
  if (window.Clerk) {
    initClerk();
  } else {
    setTimeout(waitForClerk, 100);
  }
}

// Start waiting for Clerk when the page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', waitForClerk);
} else {
  waitForClerk();
} 