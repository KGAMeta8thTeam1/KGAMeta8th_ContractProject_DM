using UnityEngine;

public class NoteSpawner : MonoBehaviour
{
    [Header("노트 프리펩")]
    [SerializeField]
    private GameObject leftNotePrefab;

    [SerializeField]
    private GameObject rightNotePrefab;

    [Header("노트 생성 간격")]
    [SerializeField]
    private float spawnInterval = 2f;

    [SerializeField]
    private float noteSpeed = 10f;

    private float timer;
    private GridManager gridManager;

    void Start()
    {
        gridManager = GridManager.Instance;
    }

    void Update()
    {
        timer += Time.deltaTime;
        if (timer >= spawnInterval)
        {
            SpawnRandomNote();
            timer = 0f;
        }
    }

    void SpawnRandomNote()
    {
        NoteData noteData = new NoteData();

        if (Random.value > 0.5f)
        {
            noteData.noteType = HitType.None;
            noteData.direction = (NoteDirection)Random.Range(0, 8);
            noteData.noteAxis = (NoteAxis)Random.Range(0, 4);
            noteData.moveSpeed = 10f;
        }
        else
        {
            noteData.noteType = Random.value > 0.5f ? HitType.Red : HitType.Blue;
            noteData.direction = NoteDirection.None;
            noteData.noteAxis = NoteAxis.None;
            noteData.moveSpeed = 10f;
        }

        bool isLeftHand = noteData.noteType == HitType.None;

        int x = isLeftHand ? Random.Range(0, 3) : Random.Range(2, 5);
        int y = Random.Range(0, gridManager.VerticalCells);

        Vector3 startPos = gridManager.GetCellPosition(gridManager.SourceGrid, x, y);
        Vector3 targetPos = gridManager.GetCellPosition(gridManager.TargetGrid, x, y);

        noteData.target = targetPos;

        GameObject prefab = isLeftHand ? leftNotePrefab : rightNotePrefab;
        GameObject note = Instantiate(prefab, startPos, Quaternion.identity);

        if (isLeftHand)
        {
            LeftNote leftNote = note.GetComponent<LeftNote>();
            if (leftNote != null)
            {
                leftNote.Initialize(noteData);
            }
        }
        else
        {
            RightNote rightNote = note.GetComponent<RightNote>();
            if (rightNote != null)
            {
                rightNote.Initialize(noteData);
            }
        }
    }
}
