using Godot;

public partial class PlayerInteractionController : Node
{
    [Export] public NodePath PlayerPath { get; set; } = "..";
    [Export] public NodePath RayCastPath { get; set; } = "../ViewPivot/Camera3D/InteractionRayCast3D";
    [Export] public NodePath PromptPath { get; set; } = "../../InteractionPrompt";

    private PlayerController _player = null!;
    private RayCast3D _rayCast = null!;
    private InteractionPrompt? _prompt;
    private IInteractable? _currentInteractable;

    public override void _Ready()
    {
        _player = GetNode<PlayerController>(PlayerPath);
        _rayCast = GetNode<RayCast3D>(RayCastPath);
        _prompt = GetNodeOrNull<InteractionPrompt>(PromptPath);
    }

    public override void _Process(double delta)
    {
        if (_player.DebugPlayerContext == PlayerContext.Seated && _player.SeatedInteractable is not null)
        {
            _currentInteractable = _player.SeatedInteractable;
            _prompt?.ShowPrompt(_currentInteractable.GetPrompt(_player));
            return;
        }

        _rayCast.ForceRaycastUpdate();
        _currentInteractable = FindInteractable(_rayCast.GetCollider() as Node);

        if (_currentInteractable is not null && _currentInteractable.CanInteract(_player))
        {
            _prompt?.ShowPrompt(_currentInteractable.GetPrompt(_player));
        }
        else
        {
            _currentInteractable = null;
            _prompt?.HidePrompt();
        }
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!@event.IsActionPressed("interact"))
        {
            return;
        }

        var interactable = _player.DebugPlayerContext == PlayerContext.Seated
            ? _player.SeatedInteractable
            : _currentInteractable;

        if (interactable is not null && interactable.CanInteract(_player))
        {
            interactable.Interact(_player);
            GetViewport().SetInputAsHandled();
        }
    }

    private static IInteractable? FindInteractable(Node? node)
    {
        while (node is not null)
        {
            if (node is IInteractable interactable)
            {
                return interactable;
            }

            node = node.GetParent();
        }

        return null;
    }
}
