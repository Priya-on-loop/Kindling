/* =========================================================
   PATTERN METADATA
   Shared between Inference and Reflection (both render the
   same 6 real dimensions from GET /api/chat/inference and
   both call the same real POST /api/user/trait/decision).

   The backend only exposes a WRITE endpoint for accept/reject
   (trait/decision) — there is no GET that returns a saved
   decision, so `feelings` is session-local UI state, not
   persisted data. It resets on reload. That's an honest
   reflection of what the API actually offers today, not a bug.
   ========================================================= */

(() => {

    const K = window.Kindling;

    K.patterns = [
        {
            id: 'builds_tinkers',
            key: 'builds_tinkers',
            label: 'Build & tinker',
            tone: 'warm',
            description: 'You tend to explore by making, testing, and changing something to see what happens.'
        },
        {
            id: 'investigates_why',
            key: 'investigates_why',
            label: 'Investigates why',
            tone: 'cool',
            description: 'You often go past the first answer and look for the reason behind how something works.'
        },
        {
            id: 'creates_expresses',
            key: 'creates_expresses',
            label: 'Create & express',
            tone: 'violet',
            description: 'Your exploration sometimes moves toward creating, communicating, or expressing an idea.'
        },
        {
            id: 'works_with_people',
            key: 'works_with_people',
            label: 'Works with people',
            tone: 'pale',
            description: 'Some of your exploration involves understanding, helping, or collaborating with others.'
        },
        {
            id: 'organizes_systems',
            key: 'organizes_systems',
            label: 'Organizes systems',
            tone: 'cool',
            description: 'You show interest in bringing structure to information, processes, and connected pieces.'
        },
        {
            id: 'leads_persuades',
            key: 'leads_persuades',
            label: 'Leads & persuades',
            tone: 'warm',
            description: 'Some activities suggest curiosity about influencing ideas, decisions, or direction.'
        }
    ];

    K.patternById = Object.fromEntries(K.patterns.map(p => [p.id, p]));

    K.feelings = {};

    K.onFeelingChange = [];

    K.setFeeling = async function setFeeling(traitKey, action) {

        const sessionId = K.getSessionId();

        if (!sessionId) {
            K.toast("Start exploring first. There's nothing to calibrate yet.");
            return;
        }

        try {

            const response = await fetch(`${K.API_BASE_URL}/api/user/trait/decision`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    trait: traitKey,
                    action: action === 'yes' ? 'accept' : 'reject'
                })
            });

            if (!response.ok) {
                K.toast("We couldn't save that right now. Please try again.");
                return;
            }

            K.feelings[traitKey] = action;

            K.onFeelingChange.forEach(fn => fn(traitKey));

            K.toast(action === 'yes' ? "Noted. We'll keep following this thread." : "Noted. We'll give this pattern less weight.");

        }

        catch (error) {
            console.error('Failed to save trait decision:', error);
            K.toast("We couldn't reach the server. Please try again.");
        }

    };

})();
