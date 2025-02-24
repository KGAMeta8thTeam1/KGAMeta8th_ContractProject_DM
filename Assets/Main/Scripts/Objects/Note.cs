using UnityEngine;

public class Note : MonoBehaviour
{
    [SerializeField, Header("블럭 타격 오차범위")]
    protected float directionalRange = 10f;

    [SerializeField, Header("노트 점수")]
    protected float NoteScore = 100;
    protected bool isMoving = true;
    protected NoteData noteData;
    protected Transform noteTrans;
    protected Vector3 hitDirection;

    public virtual void Initialize(NoteData data)
    {
        noteData = new NoteData()
        {
            noteAxis = data.noteAxis,
            direction = data.direction,
            target = data.target,
            moveSpeed = data.moveSpeed,
            noteType = data.noteType,
        };
        noteTrans = GetComponent<Transform>();
        NoteDirectionChange();
        NoteHitDirectionChange();
    }

    protected virtual void Update()
    {
        if (isMoving)
        {
            transform.position = Vector3.MoveTowards(
                transform.position,
                noteData.target,
                noteData.moveSpeed * Time.deltaTime
            );

            if (Vector3.Distance(transform.position, noteData.target) < 0.1f)
            {
                Destroy(gameObject);
            }
        }
    }

    private void NoteDirectionChange()
    {
        float rotationZ = 0f;
        switch (noteData.direction)
        {
            case NoteDirection.East:
                rotationZ = 90f;
                hitDirection = SetHitDirection(new Vector3(1, 0, 0));
                break;
            case NoteDirection.West:
                rotationZ = -90f;
                hitDirection = SetHitDirection(new Vector3(-1, 0, 0));
                break;
            case NoteDirection.South:
                rotationZ = 0f;
                hitDirection = SetHitDirection(new Vector3(0, -1, 0));
                break;
            case NoteDirection.North:
                rotationZ = 180f;
                hitDirection = SetHitDirection(new Vector3(0, 1, 0));
                break;
            case NoteDirection.Northeast:
                rotationZ = 135f;
                hitDirection = SetHitDirection(new Vector3(1, 1, 0).normalized);
                break;
            case NoteDirection.Northwest:
                rotationZ = -135f;
                hitDirection = SetHitDirection(new Vector3(-1, 1, 0).normalized);
                break;
            case NoteDirection.Southeast:
                rotationZ = 45f;
                hitDirection = SetHitDirection(new Vector3(1, -1, 0).normalized);
                break;
            case NoteDirection.Southwest:
                rotationZ = -45f;
                hitDirection = SetHitDirection(new Vector3(-1, -1, 0).normalized);
                break;
        }
        noteTrans.rotation = Quaternion.Euler(
            noteTrans.rotation.eulerAngles.x,
            noteTrans.rotation.eulerAngles.y,
            rotationZ
        );
    }

    private void NoteHitDirectionChange()
    {
        float rotationY = 0f;
        switch (noteData.noteAxis)
        {
            case NoteAxis.PZ:
                rotationY = 0f;
                break;
            case NoteAxis.MZ:
                rotationY = 180f;
                break;
            case NoteAxis.PX:
                rotationY = 90f;
                break;
            case NoteAxis.MX:
                rotationY = -90f;
                break;
        }
        noteTrans.rotation = Quaternion.Euler(
            noteTrans.rotation.eulerAngles.x,
            rotationY,
            noteTrans.rotation.eulerAngles.z
        );
    }

    private Vector3 SetHitDirection(Vector3 dir)
    {
        switch (noteData.noteAxis)
        {
            case NoteAxis.PZ:
                return dir;
            case NoteAxis.MZ:
                return dir = -dir;
            case NoteAxis.PX:
                return new Vector3(dir.z, dir.y, -dir.x);
            case NoteAxis.MX:
                return new Vector3(dir.z, dir.y, dir.x);
            default:
                return dir;
        }
    }
}
