using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

public class CombinedSpawnManager : MonoBehaviour
{
    [Header("그리드 노트 설정")]
    [SerializeField] private GameObject leftNotePrefab;
    [SerializeField] private GameObject rightNotePrefab;
    [SerializeField] private float gridNoteSpeed = 10f;
    [SerializeField] private float gridSpawnInterval = 2f;
    
    [Header("원형 노트 설정")]
    [SerializeField] private float sourceRadius = 5f;
    [SerializeField] private float targetRadius = 5f;
    [SerializeField] private GameObject primarySegmentPrefab;
    [SerializeField] private GameObject symmetricSegmentPrefab;
    [SerializeField] private float arcMoveSpeed = 5f;
    [SerializeField] private int segmentCount = 36;
    [SerializeField] private float segmentSpawnInterval = 0.1f;
    [SerializeField] private bool createSymmetric = true;
    
    [Header("원형 위치 설정")]
    [SerializeField] private float circleZOffset = 0f; // 그리드로부터 Z축 오프셋
    [SerializeField] private float circleYOffset = 0f; // 그리드로부터 Y축 오프셋
    
    [Header("이펙트 설정")]
    [SerializeField] private GameObject hitEffectPrefab; // 충돌 시 생성할 이펙트

    private GridManager gridManager;
    private Vector3 sourceCenter;
    private Vector3 targetCenter;
    private List<Vector3> sourcePoints = new List<Vector3>();
    private List<Vector3> targetPoints = new List<Vector3>();
    private float gridTimer;
    
    private void Start()
    {
        gridManager = GridManager.Instance;
        
        if (gridManager == null)
        {
            Debug.LogError("GridManager를 찾을 수 없습니다!");
            return;
        }
        
        // 그리드의 오른쪽 3x3 영역 중앙을 기준으로 원형 위치 계산
        int rightGridCenterX = gridManager.TotalHorizontalCells - gridManager.HandGridSize / 2 - 1;
        int gridCenterY = gridManager.VerticalCells / 2;
        
        // 소스 그리드의 오른쪽 영역 중앙 위치 계산
        Vector3 sourceGridCenter = gridManager.GetCellPosition(
            gridManager.SourceGrid, 
            rightGridCenterX, 
            gridCenterY
        );
        
        // 타겟 그리드의 오른쪽 영역 중앙 위치 계산
        Vector3 targetGridCenter = gridManager.GetCellPosition(
            gridManager.TargetGrid, 
            rightGridCenterX, 
            gridCenterY
        );
        
        // 원형 중심점 설정
        sourceCenter = new Vector3(
            sourceGridCenter.x,
            sourceGridCenter.y + circleYOffset,
            sourceGridCenter.z + circleZOffset
        );
        
        targetCenter = new Vector3(
            targetGridCenter.x,
            targetGridCenter.y + circleYOffset,
            targetGridCenter.z + circleZOffset
        );
        
        // 원형 포인트 생성
        GenerateCirclePoints();
        
        // 프리팹 확인
        if (primarySegmentPrefab == null)
        {
            Debug.LogWarning("기본 세그먼트 프리팹이 설정되지 않았습니다. 기본 큐브를 사용합니다.");
            primarySegmentPrefab = GameObject.CreatePrimitive(PrimitiveType.Cube);
            primarySegmentPrefab.transform.localScale = new Vector3(0.3f, 0.3f, 0.3f);
            DestroyImmediate(primarySegmentPrefab.GetComponent<Collider>());
        }
        
        if (symmetricSegmentPrefab == null)
        {
            Debug.LogWarning("대칭 세그먼트 프리팹이 설정되지 않았습니다. 기본 구체를 사용합니다.");
            symmetricSegmentPrefab = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            symmetricSegmentPrefab.transform.localScale = new Vector3(0.3f, 0.3f, 0.3f);
            DestroyImmediate(symmetricSegmentPrefab.GetComponent<Collider>());
        }
    }
    
    private void Update()
    {
        // 그리드 노트 생성 타이머
        gridTimer += Time.deltaTime;
        if (gridTimer >= gridSpawnInterval)
        {
            SpawnGridNote();
            gridTimer = 0f;
        }
        
        // 스페이스바를 누르면 원형 롱노트 생성
        if (Keyboard.current != null && Keyboard.current.spaceKey.wasPressedThisFrame)
        {
            SpawnRandomArcLongNote();
        }
    }
    
    private void SpawnGridNote()
    {
        NoteData noteData = new NoteData();
        bool isLeftHand = Random.value > 0.5f; // 50% 확률로 왼쪽/오른쪽 결정
        
        if (isLeftHand)
        {
            noteData.noteType = NoteHitType.Hand; // 또는 왼쪽 노트용 타입
        }
        else
        {
            noteData.noteType = Random.value > 0.5f ? NoteHitType.Red : NoteHitType.Blue;
        }
        
        noteData.direction = (NoteDirection)Random.Range(1, 8);
        noteData.noteAxis = NoteAxis.PZ;
        noteData.moveSpeed = gridNoteSpeed;
        
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
    
    private void GenerateCirclePoints()
    {
        sourcePoints.Clear();
        targetPoints.Clear();
        
        float angleStep = 360f / segmentCount;
        
        // 소스 원형 포인트 생성 (XY 평면에 세로로 배치)
        for (int i = 0; i < segmentCount; i++)
        {
            float angle = i * angleStep;
            float radians = angle * Mathf.Deg2Rad;
            
            // XY 평면에서 원을 생성 (세로 원)
            float x = sourceCenter.x + sourceRadius * Mathf.Cos(radians);
            float y = sourceCenter.y + sourceRadius * Mathf.Sin(radians);
            float z = sourceCenter.z;
            
            sourcePoints.Add(new Vector3(x, y, z));
        }
        
        // 타겟 원형 포인트 생성 (XY 평면에 세로로 배치)
        for (int i = 0; i < segmentCount; i++)
        {
            float angle = i * angleStep;
            float radians = angle * Mathf.Deg2Rad;
            
            // XY 평면에서 원을 생성 (세로 원)
            float x = targetCenter.x + targetRadius * Mathf.Cos(radians);
            float y = targetCenter.y + targetRadius * Mathf.Sin(radians);
            float z = targetCenter.z;
            
            targetPoints.Add(new Vector3(x, y, z));
        }
        
        Debug.Log($"원형 경로 생성 완료: 소스 포인트 {sourcePoints.Count}개, 타겟 포인트 {targetPoints.Count}개");
    }
    
    private void SpawnRandomArcLongNote()
    {
        // 랜덤 시작 인덱스와 호의 길이 선택
        int startIdx = Random.Range(0, segmentCount);
        int arcLength = Random.Range(5, 15); // 호의 길이 (세그먼트 수)
        
        SpawnArcLongNote(startIdx, arcLength);
    }
    
    public void SpawnArcLongNote(int startIndex, int arcLength)
    {
        if (startIndex < 0 || startIndex >= segmentCount)
        {
            Debug.LogError($"잘못된 시작 인덱스: {startIndex}");
            return;
        }
        
        // 호의 끝 인덱스 계산 (원형 배열이므로 모듈로 연산)
        int endIndex = (startIndex + arcLength) % segmentCount;
        
        // 첫 번째 호 생성 (기본 프리팹 사용)
        StartCoroutine(SpawnArcSegments(startIndex, endIndex, false));
        
        // 대칭 호 생성 (옵션이 활성화된 경우, 대칭 프리팹 사용)
        if (createSymmetric)
        {
            // 대칭 시작점과 끝점 계산 (원의 반대편)
            int symmetricStart = (startIndex + segmentCount / 2) % segmentCount;
            int symmetricEnd = (endIndex + segmentCount / 2) % segmentCount;
            
            StartCoroutine(SpawnArcSegments(symmetricStart, symmetricEnd, true));
            
            Debug.Log($"대칭 호 롱노트 생성: 시작 {symmetricStart}, 끝 {symmetricEnd}");
        }
        
        Debug.Log($"호 롱노트 생성: 시작 {startIndex}, 끝 {endIndex}, 길이 {arcLength}");
    }
    
    private IEnumerator SpawnArcSegments(int startIndex, int endIndex, bool isSymmetric)
    {
        // 시계 방향으로 이동할지 결정
        bool clockwise = true;
        int currentIndex = startIndex;
        int segmentsSpawned = 0;
        
        // 사용할 프리팹 선택
        GameObject prefabToUse = isSymmetric ? symmetricSegmentPrefab : primarySegmentPrefab;
        
        // 호의 모든 세그먼트를 순차적으로 생성
        while (true)
        {
            // 현재 인덱스의 소스 및 타겟 위치
            Vector3 sourcePos = sourcePoints[currentIndex];
            Vector3 targetPos = targetPoints[currentIndex];
            
            // 선택된 프리팹으로 세그먼트 생성
            GameObject segment = Instantiate(prefabToUse, sourcePos, Quaternion.identity);
            
            // 세그먼트 이동 컴포넌트 추가
            ArcSegmentMover mover = segment.AddComponent<ArcSegmentMover>();
            mover.Initialize(sourcePos, targetPos, arcMoveSpeed);

            //충돌 이펙트 설정
            if(hitEffectPrefab != null)
            {
                mover.SetHitEffect(hitEffectPrefab);
            }
            
            segmentsSpawned++;
            
            // 끝 인덱스에 도달했는지 확인
            if (currentIndex == endIndex)
            {
                break;
            }
            
            // 다음 인덱스로 이동 (시계 또는 반시계 방향)
            if (clockwise)
            {
                currentIndex = (currentIndex + 1) % segmentCount;
            }
            else
            {
                currentIndex = (currentIndex - 1 + segmentCount) % segmentCount;
            }
            
            // 세그먼트 생성 간격만큼 대기
            yield return new WaitForSeconds(segmentSpawnInterval);
        }
        
        string symmetricText = isSymmetric ? "대칭 " : "";
        Debug.Log($"{symmetricText}호 롱노트 생성 완료: {segmentsSpawned}개 세그먼트");
    }
    
    // 디버그용 시각화
    private void OnDrawGizmos()
    {
        if (!Application.isPlaying) return;
        
        // 소스 원형 그리기
        Gizmos.color = Color.green;
        DrawCircle(sourceCenter, sourceRadius, segmentCount, true);
        
        // 타겟 원형 그리기
        Gizmos.color = Color.red;
        DrawCircle(targetCenter, targetRadius, segmentCount, true);
        
        // 플레이 모드에서 실제 포인트 표시
        if (Application.isPlaying)
        {
            Gizmos.color = Color.yellow;
            for (int i = 0; i < sourcePoints.Count; i++)
            {
                Gizmos.DrawSphere(sourcePoints[i], 0.1f);
            }
            
            Gizmos.color = Color.cyan;
            for (int i = 0; i < targetPoints.Count; i++)
            {
                Gizmos.DrawSphere(targetPoints[i], 0.1f);
            }
        }
    }
    
    private void DrawCircle(Vector3 center, float radius, int segments, bool vertical)
    {
        float angleStep = 360f / segments;
        Vector3 prevPoint;
        
        if (vertical)
        {
            // XY 평면에 세로 원 그리기
            prevPoint = new Vector3(
                center.x + radius * Mathf.Cos(0),
                center.y + radius * Mathf.Sin(0),
                center.z
            );
        }
        else
        {
            // XZ 평면에 가로 원 그리기 (기존 방식)
            prevPoint = new Vector3(
                center.x + radius * Mathf.Sin(0),
                center.y,
                center.z + radius * Mathf.Cos(0)
            );
        }
        
        for (int i = 1; i <= segments; i++)
        {
            float angle = i * angleStep;
            float radians = angle * Mathf.Deg2Rad;
            Vector3 point;
            
            if (vertical)
            {
                // XY 평면에 세로 원 그리기
                point = new Vector3(
                    center.x + radius * Mathf.Cos(radians),
                    center.y + radius * Mathf.Sin(radians),
                    center.z
                );
            }
            else
            {
                // XZ 평면에 가로 원 그리기 (기존 방식)
                point = new Vector3(
                    center.x + radius * Mathf.Sin(radians),
                    center.y,
                    center.z + radius * Mathf.Cos(radians)
                );
            }
            
            Gizmos.DrawLine(prevPoint, point);
            prevPoint = point;
        }
        
        Gizmos.DrawSphere(center, 0.3f);
    }
}
