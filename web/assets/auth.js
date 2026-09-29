// auth.js

// ========================================
// LOGOUT
// ========================================
async function logout(event) {

    // Prevent the <a href="home.html"> from
    // navigating before the logout request finishes.
    if (event) {
        event.preventDefault();
    }

    // Ask for confirmation
    const confirmed = confirm("Are you sure you want to logout?");

    if (!confirmed) {
        return;
    }

    try {

        // Send logout request to the backend.
        // The backend will clear the SessionMiddleware session.
        const response = await fetch("/auth_logout_user", {
            method: "POST",
            credentials: "same-origin"
        });

        // Logout successful
        if (response.ok) {

            // Redirect after the backend session
            // has been successfully cleared.
            window.location.replace("/home.html");

            return;
        }

        // Backend returned an error
        console.error(
            "Logout failed:",
            response.status,
            response.statusText
        );

        alert("Logout failed. Please try again.");

    } catch (error) {

        // Network/server error
        console.error("Logout error:", error);

        alert(
            "Unable to connect to the server. " +
            "Please check your connection and try again."
        );
    }
}
