using Godot;

public partial class InteractionPrompt : CanvasLayer
{
    private Label _label = null!;

    public override void _Ready()
    {
        _label = GetNode<Label>("Panel/MarginContainer/Label");
        HidePrompt();
    }

    public void ShowPrompt(string text)
    {
        _label.Text = text;
        Visible = true;
    }

    public void HidePrompt()
    {
        Visible = false;
    }
}

