using UnityEngine;

public class GridManager : Singleton<GridManager>
{
    [SerializeField]
    private int totalHorizontalCells = 5;

    [SerializeField]
    private int verticalCells = 3;

    [SerializeField]
    private int handGridSize = 3;

    [SerializeField]
    private float cellSize = 1f;

    [SerializeField]
    private float cellSpacing = 0.1f;

    [SerializeField]
    private float gridDistance = 15f;

    [SerializeField]
    private Material leftHandMaterial;

    [SerializeField]
    private Material rightHandMaterial;

    [SerializeField]
    private Material overlapMaterial;

    private Transform sourceGrid;
    private Transform targetGrid;

    public Transform SourceGrid => sourceGrid;
    public Transform TargetGrid => targetGrid;
    public Vector2Int GridSize => new Vector2Int(totalHorizontalCells, verticalCells);
    public int TotalHorizontalCells => totalHorizontalCells;
    public int VerticalCells => verticalCells;
    public int HandGridSize => handGridSize;
    public float CellSize => cellSize;
    public float GridDistance => gridDistance;

    protected override void Awake()
    {
        base.Awake();
        CreateGrids();
    }

    void CreateGrids()
    {
        GameObject sourceObj = new GameObject("SourceGrid");
        sourceGrid = sourceObj.transform;
        sourceGrid.parent = transform;
        sourceGrid.localPosition = new Vector3(0, 1.7f, 2f);
        sourceGrid.localRotation = Quaternion.Euler(0, 180, 0);
        CreateGrid(sourceGrid, false);

        GameObject targetObj = new GameObject("TargetGrid");
        targetGrid = targetObj.transform;
        targetGrid.parent = transform;
        targetGrid.localPosition = new Vector3(0, 1.7f, gridDistance);
        targetGrid.localRotation = Quaternion.Euler(0, 180, 0);
        CreateGrid(targetGrid, true);
    }

    void CreateGrid(Transform gridParent, bool isTarget)
    {
        float totalWidth =
            (totalHorizontalCells * cellSize) + ((totalHorizontalCells - 1) * cellSpacing);
        float totalHeight = (verticalCells * cellSize) + ((verticalCells - 1) * cellSpacing);
        float startX = -totalWidth / 2f;
        float startY = -totalHeight / 2f;

        for (int x = 0; x < totalHorizontalCells; x++)
        {
            for (int y = 0; y < verticalCells; y++)
            {
                int gridX = isTarget ? (totalHorizontalCells - 1 - x) : x;
                CreateCell(gridParent, x, y, startX, startY);
            }
        }
    }

    void CreateCell(Transform parent, int x, int y, float startX, float startY)
    {
        GameObject cell = new GameObject($"Cell_{x}_{y}");
        cell.transform.parent = parent;

        float xPos = startX + (x * (cellSize + cellSpacing));
        float yPos = startY + (y * (cellSize + cellSpacing));
        cell.transform.localPosition = new Vector3(xPos, yPos, 0);

        GameObject visual = GameObject.CreatePrimitive(PrimitiveType.Cube);
        visual.transform.parent = cell.transform;
        visual.transform.localPosition = Vector3.zero;
        visual.transform.localScale = new Vector3(cellSize, cellSize, 0.1f);

        MeshRenderer renderer = visual.GetComponent<MeshRenderer>();
        if (x < handGridSize)
        {
            renderer.material = leftHandMaterial;
        }
        if (x >= totalHorizontalCells - handGridSize)
        {
            renderer.material = rightHandMaterial;
        }
        if (x >= handGridSize - 1 && x < totalHorizontalCells - handGridSize + 1)
        {
            renderer.material = overlapMaterial;
        }

        CellInfo cellInfo = cell.AddComponent<CellInfo>();
        cellInfo.Initialize(x, y, IsLeftHand(x), IsRightHand(x));
    }

    public bool IsLeftHand(int x)
    {
        return x < handGridSize;
    }

    public bool IsRightHand(int x)
    {
        return x >= totalHorizontalCells - handGridSize;
    }

    public Vector3 GetCellPosition(Transform gridTransform, int x, int y)
    {
        float totalWidth =
            (totalHorizontalCells * cellSize) + ((totalHorizontalCells - 1) * cellSpacing);
        float totalHeight = (verticalCells * cellSize) + ((verticalCells - 1) * cellSpacing);
        float startX = -totalWidth / 2f;
        float startY = -totalHeight / 2f;

        float xPos = startX + (x * (cellSize + cellSpacing));
        float yPos = startY + (y * (cellSize + cellSpacing));

        return gridTransform.TransformPoint(new Vector3(xPos, yPos, 0));
    }
}
