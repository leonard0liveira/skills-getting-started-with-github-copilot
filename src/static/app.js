document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const messageDiv = document.getElementById("message");

  function createInfoParagraph(label, value) {
    const paragraph = document.createElement("p");
    const strong = document.createElement("strong");

    strong.textContent = `${label}: `;
    paragraph.append(strong, value);

    return paragraph;
  }

  function createParticipantListItem(activityName, participant) {
    const listItem = document.createElement("li");
    const name = document.createElement("span");
    const removeButton = document.createElement("button");

    name.textContent = participant;

    removeButton.className = "remove-participant-button";
    removeButton.type = "button";
    removeButton.ariaLabel = `Remove ${participant} from ${activityName}`;
    removeButton.title = "Remove participant";
    removeButton.dataset.activity = activityName;
    removeButton.dataset.email = participant;
    removeButton.textContent = "×";

    listItem.append(name, removeButton);

    return listItem;
  }

  function createActivityCard(name, details) {
    const activityCard = document.createElement("div");
    const heading = document.createElement("h4");
    const description = document.createElement("p");
    const participantsSection = document.createElement("div");
    const participantsLabel = document.createElement("strong");
    const participantsList = document.createElement("ul");
    const spotsLeft = details.max_participants - details.participants.length;

    activityCard.className = "activity-card";
    heading.textContent = name;
    description.textContent = details.description;
    participantsSection.className = "participants-section";
    participantsList.className = "participants-list";
    participantsLabel.textContent = "Participants:";

    if (details.participants.length) {
      details.participants.forEach((participant) => {
        participantsList.appendChild(createParticipantListItem(name, participant));
      });
    } else {
      const emptyState = document.createElement("li");

      emptyState.className = "no-participants";
      emptyState.textContent = "No participants yet";
      participantsList.appendChild(emptyState);
    }

    participantsSection.append(participantsLabel, participantsList);
    activityCard.append(
      heading,
      description,
      createInfoParagraph("Schedule", details.schedule),
      createInfoParagraph("Availability", `${spotsLeft} spots left`),
      participantsSection
    );

    return activityCard;
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";
      activitySelect.replaceChildren();

      const defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.textContent = "-- Select an activity --";
      activitySelect.appendChild(defaultOption);

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = createActivityCard(name, details);

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });
    } catch (error) {
      activitiesList.innerHTML = "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  activitiesList.addEventListener("click", async (event) => {
    const removeButton = event.target.closest(".remove-participant-button");
    if (!removeButton) return;

    const { activity, email } = removeButton.dataset;
    removeButton.disabled = true;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/participants?email=${encodeURIComponent(email)}`,
        { method: "DELETE" }
      );

      if (!response.ok) {
        throw new Error("Failed to remove participant");
      }

      await fetchActivities();
    } catch (error) {
      removeButton.disabled = false;
      console.error("Error removing participant:", error);
    }
  });

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const activity = document.getElementById("activity").value;

    try {
      const response = await fetch(
        `/activities/${encodeURIComponent(activity)}/signup?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        messageDiv.textContent = result.message;
        messageDiv.className = "success";
        signupForm.reset();
        await fetchActivities();
      } else {
        messageDiv.textContent = result.detail || "An error occurred";
        messageDiv.className = "error";
      }

      messageDiv.classList.remove("hidden");

      // Hide message after 5 seconds
      setTimeout(() => {
        messageDiv.classList.add("hidden");
      }, 5000);
    } catch (error) {
      messageDiv.textContent = "Failed to sign up. Please try again.";
      messageDiv.className = "error";
      messageDiv.classList.remove("hidden");
      console.error("Error signing up:", error);
    }
  });

  // Initialize app
  fetchActivities();
});
