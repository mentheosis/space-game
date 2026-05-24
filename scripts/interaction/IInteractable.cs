public interface IInteractable
{
    string GetPrompt(PlayerController player);
    bool CanInteract(PlayerController player);
    void Interact(PlayerController player);
}

