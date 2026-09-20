document.addEventListener("DOMContentLoaded", () => {

    const editButtons = document.querySelectorAll(".profile-edit");

    editButtons.forEach((button) => {

        button.addEventListener("click", () => {

            const pattern = button.dataset.pattern;

            /*
             * Backend integration will be added later.
             *
             * Eventually this action will allow the user to:
             * - accept a pattern
             * - reject a pattern
             * - edit a pattern
             *
             * For now we only provide visual feedback.
             */

            button.textContent = "Selected";

            setTimeout(() => {
                button.textContent = "Edit";
            }, 1000);

            console.log(`Edit requested for: ${pattern}`);
        });

    });

});