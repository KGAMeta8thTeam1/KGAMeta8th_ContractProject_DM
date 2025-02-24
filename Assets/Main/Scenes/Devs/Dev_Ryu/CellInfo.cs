using UnityEngine;

public class CellInfo : MonoBehaviour
{
    public int X { get; private set; }
    public int Y { get; private set; }
    public bool IsLeftHand { get; private set; }
    public bool IsRightHand { get; private set; }

    public void Initialize(int x, int y, bool isLeft, bool isRight)
    {
        X = x;
        Y = y;
        IsLeftHand = isLeft;
        IsRightHand = isRight;
    }
}
