
# 변경점

- v1.2.21
    - 코드 정리
- v1.2.21
    - 스캔 액티비티 확인시 섹션ID를 조건에 추가
- v1.2.20
    - 페이지에 소켓IO 적용
- v1.2.19
    - 자바스크립트 정리
    - 목록 html 정리
- v1.2.18
    - 구드공 툴 DB 정리 오류 수정
    - 일부 명령 요청 방식 수정
- v1.2.17
    - 자바스크립트 정리
- v1.2.16
    - 일정 일괄 수정 기능 추가
    - 일정 추가/편집 모달을 ESC 키로 닫기 활성화
- v1.1.16
    - Plex 휴지통 스캔의 동작 버튼 수정
- v1.1.15
    - Plexmate 시간초과 항목 점검 기능 수정
- v1.1.14
    - 일부 코드 구조 수정
- v1.1.13
    - 접속 로그 기능 추가
    - 도구의 기타 설정을 기본 설정으로 이동
- v1.0.13
    - 체크박스 작동 방식 변경
- v1.0.12
    - 일정 목록 일부 디자인 변경
- v1.0.11
    - Rclone remote 접속 확인 버그 수정
- v1.0.10
    - 최근 완료 순으로 정렬 추가
- v1.0.9
    - 일정 항목을 목록에서 선택 삭제
- v1.0.8
    - 오타 수정
- v1.0.7
    - 일정 검색 옵션 추가
- v1.0.6
    - 휴지통 비우기 실행 전 스캐닝 상태 확인
- v1.0.5
    - vfs 리모트를 목록에서 선택
    - 일정 저장시 잘못된 문구 출력 수정
    - 플러그인 로딩시 휴지통 작업 상태 초기화
- v1.0.4
    - 리팩토링
- v1.0.3
    - 라이브러리 경로 비교식 변경 및 기타 수정
- v1.0.2
    - `celery`가 적용되지 않는 문제 수정
    - 일부 기능에 `socket.io` 적용
- v1.0.1
    - `스캔`이 포함된 작업은 플렉스 라이브러리에 등록된 경로를 대상으로 실행됩니다.
    - 작업 대상으로 플렉스 라이브러리 섹션을 지정할 수 있습니다.

# 할 수 있는 것

- 새로고침

    Rclone의 리모트 서버에 vfs/refresh 요청
- 스캔

    Plex 서버에 Web API 스캔을 요청
- 시작 스크립트

    시작시 한번 실행되어 Flaskfarm 실행에 필요한 쉘 커맨드를 실행
- Plexmate 파일 정리

    Plexmate의 라이브러리 파일 정리를 일정으로 등록
- Plex 휴지통 스캔

    Plex의 이용불가 파일들을 조회 후 새로고침 및 스캔
- gds_tool 플러그인의 DB 정리

- Flaskfarm 로그인 로그

- Flaskfarm 엑세스 로그

# 필요한 것

- plex_mate 플러그인

- gds_tool 플러그인

- Rclone Remote Control 서버


# 설정하는 법

## Rclone Remote

- ### Rclone Remote 주소

    리모트 주소와 필요할 경우 User, Pass를 입력한 다음 접속 확인버튼을 클릭합니다.
    정상 접속될 경우 `vfs/list` 결과가 나타나고 리모트 항목에 자동으로 첫번째 vfs가 입력됩니다.

- ### 경로 변경 규칙(필수)

    로컬 경로를 rclone 리모트의 경로로 변경할 때 사용할 규칙입니다. 마운트한 로컬 경로와 rclone 리모트의 경로가 다르기 때문에 이를 변경하는 과정이 필요합니다.
    콜론(:)의 앞쪽에는 로컬 경로중 변경되어야 하는 부분을 입력합니다. 콜론(:)의 뒷쪽에는 앞서 입력한 부분을 어떻게 변경할 것인지 지정해 주세요.

    /변경해야/하는/로컬/경로:/리모트/경로에/맞춰/변경된/경로

    예를 들어 아래와 같이 마운트를 한 상황이라고 가정해 보겠습니다.
    ```
    rclone mount /mnt/gds gds:

    로컬 경로: /mnt/gds/VOD/1.방송중/드라마
    리모트 경로: VOD/1.방송중/드라마
    ```
    로컬 경로의 `/mnt/gds` 부분은 gds 리모트에 존재하지 않는 경로이기 때문에 삭제해야 합니다.

    그럴 경우 아래처럼 `/mnt/gds` 부분을 삭제(공백으로 변환)하는 규칙을 설정하면 됩니다.
    ```
    /mnt/gds:
    ```

    추가로 gds의 루트 폴더가 아닌 임의의 폴더를 마운트한 상황을 가정해 보겠습니다.

    ```
    rclone mount /mnt/gds/onair/예능 gds:VOD/1.방송중/예능

    로컬 경로: /mnt/gds/onair/예능
    리모트 경로: VOD/1.방송중/예능
    ```

    로컬 경로의 `/mnt/gds/onair/` 부분은 gds 리모트에 존재하지 않는 경로라서 변경이 필요합니다.

    아래처럼 로컬 경로의 `/mnt/gds/onair` 부분을 `/VOD/1.방송중` 으로 변경하는 규칙을 설정합니다.
    ```
    /mnt/gds/onair:/VOD/1.방송중
    ```

## Plexmate

- ### 최대 스캔 시간

    Plexmate의 스캔 항목 중에서 `SCANNING` 상태가 이 시간을 초과하여 지속될 경우 스캔 실패로 간주합니다. 해당 항목들은 다음 `Plexmate Ready 새로고침`이 실행될 때 `FINISH_TIMEOVER`로 변경됩니다. 아래의 상황을 회피하기 위한 기능입니다.

    - `SCANNING` 상태인 폴더에 새로운 미디어가 추가 됐을 때 스캔되지 않고 `FINISH_ALREADY_IN_QUEUE` 상태로 종료될 수 있습니다.


- ### 타임오버 항목 범위

    Plexmate의 파일 체크 테스트를 통과하지 못해 `TIMEOVER`된 항목들을 다시 스캔 할 때 사용합니다. Plexmate Ready 새로고침이 실행되면 이 ID 범위내의 `TIMEOVER` 항목들은 다시 `READY`로 변경합니다. 계속해서 `TIMEOVER`가 되는 항목은 점검후 수동으로 DB 삭제해 주세요. 시작 ID 번호와 끝 ID 번호를 ~ 물결표시로 구분해 주세요. 예: 456~501

    ```
    456~501
    ```


- ### PLEX 경로 변경 규칙

    Flaskfarm의 로컬 경로와 플렉스의 로컬 경로가 다를 경우 입력해 주세요. Rclone 경로 변경 규칙과 동일한 방식으로 입력해 주면 됩니다.


## 구드공 툴
`gds_tool` 플러그인의 DB를 정리할 때 사용합니다.

- ### 잔여 기간

    단위는 `일`입니다. 현재부터 `잔여 기간`(일)까지의 레코드만 남기고 `잔여 기간` 이전의 레코드는 모두 삭제합니다. 전체 레코드를 삭제할 경우 `잔여 기간`에 `0`을 입력하세요.

- ### 자동 삭제

    FF가 재시작 되고 플러그인이 로딩되면 `잔여 기간`에 따라 DB를 정리합니다.


## 시작 스크립트

Flaskfarm이 시작될 때 실행이 필요한 명령어들을 실행하는 기능을 설정합니다.

- ### 실행 허용

    명령어 실행 여부를 설정합니다. 로그에서 어떤 명령어가 실행될 예정인지 확인한 후 실행 여부를 결정하세요.


- ### 실행할 명령어

    간단한 쉘 커맨드를 한 줄씩 입력하세요.

    리눅스 예시
    ```
    apt-get update
    ls -al /home
    ```

    윈도우 예시
    ```
    cmd.exe /c calc
    cmd.exe /c dir c:
    ```


- ### 명령어 최대 대기 시간

    실행한 명령어 프로세스의 응답 대기 시간입니다.


- ### 플러그인 의존성 목록

    플러그인 별로 필요한 타플러그인이나 명령어를 모아 놓은 목록입니다. `/data/db/flaskfarmaider.yaml` 파일을 수정하거나 설정에서 yaml 문법으로 작성해 주세요. 설치된 플러그인의 요구사항들을 이 목록에서 확인 후 시작시 실행합니다. 윈도우의 경우 패키지 설치 방식을 정규화하기 힘든 관계로 `packages` 목록을 무시합니다. 윈도우용 패키지 설치 명령어는 `commands` 목록이나 `실행할 명령어`에서 실행해 주세요.


## 기타 로그

- ### 로그인 로그

    `flaskfarm`의 로그인 시도 결과를 로그로 남깁니다. 로그는 `system.log`에 기록됩니다.

    ```
    [2023-09-09 22:04:06,081|WARNING|presenters.py:697] 로그인 실패: user=nimda ip=123.456.789.123
    [2023-09-09 22:04:11,727|INFO|presenters.py:703] 로그인 성공: user=admin ip=123.456.789.123
    ```
- ### 접속 로그

    `flaskfarm`의 접속 로그를 남깁니다.

- ### 접속 로그 경로

    접속 로그 파일의 기본값은 `/data/log/access.log`입니다.

- ### 접속 로그 형식

    접속 로그의 출력 형식을 지정합니다.

    - {remote}: 클라이언트 IP
    - {method}: HTTP 메소드 (GET, POST, ...)
    - {path}: 요청 경로
    - {status}: HTTP 상태 코드(200, 404, ...)
    - {length}: Content-Length
    - {agent}: User-Agent

    ```
    e.g. {remote} {method} "{path}" {status}

    [2023-12-31 01:39:19,735] 127.0.0.1 GET "/flaskfarmaider/setting?" 200
    ```


# 사용하는 법

## 작업을 실행시키는 방법

### 1. 작업 일정을 만들어서 주기마다 실행

#### 일정 추가 창의 옵션들

- **작업**: 실행하고자 하는 작업을 선택
    - **새로고침 후 스캔**: 대상 경로 혹은 하위 경로가 플렉스 라이브러리 경로에 해당되면 `vfs/refresh` 후 스캔합니다.
    - **새로고침**: 대상 경로 혹은 하위 경로를 `vfs/refresh` 를 실행합니다.
    - **스캔**: 대상 경로 혹은 하위 경로가 플렉스 라이브러리 경로에 해당되면 스캔합니다.
    - **Plexmate Ready 새로고침**: `plex_mate` 플러그인의 스캔 목록 중에서 파일 체크를 대기중인 항목을 `vfs/refresh` 합니다.
    - **Plexmate 파일 정리**: `plex_mate` 플러그인의 파일 정리를 실행합니다.
    - **시작 스크립트**: `flaskfarm`이 시작될 때 필요한 명령어를 실행됩니다.
- **설명**: 일정 목록에 표시되는 간단한 제목
- **로컬 경로**: 작업의 대상이 되는 로컬 파일 경로
- **라이브러리 섹션**: 로컬 경로와 비교하여 하위인 경로가 작업의 대상으로 선택됩니다.
- **VFS 리모트**: Rclone 리모트 콘트롤 서버에 요청을 보낼 리모트 이름 (`vfs/list`로 확인 가능)
- **recursive**: 선택한 작업에 `vfs/refresh` 과정이 포함되어 있을 경우 `--recursive` 옵션을 적용
- **스캔 방식**
    - **Plexmate 스캔**: Plexmate 플러그인으로 scan 요청
    - **주기적 스캔**: Plexmate 플러그인의 주기적 스캔을 실행
    - **Plex Web API**: Plex 서버로 직접 스캔 요청
- **주기적 스캔 작업**: 스캔 방식이 `주기적 스캔`일 경우 주기적 스캔의 작업 목록중 선택
- **파일 정리 유형**: Plexmate의 파일 정리 라이브러리 타입
- **파일 정리 단계**: Plexmate의 파일 정리 단계
- **파일 정리 섹션**: Plexmate로 파일 정리할 대상 라이브러리
- **일정 방식**
    - **없음**: 일정 목록에만 표시하고 실제로는 실행되지 않음
    - **시작시 실행**: Flaskfarm이 시작되면 1회 실행
    - **시간 간격**: 시간 간격 옵션에 따라 해당 주기마다 실행
- **시간 간격**: 분 단위 혹은 cron 시간 표현식
- **시작시 일정 등록**: Flaskfarm이 시작되면 자동으로 해당 일정을 활성화


#### 작업 별 일정 추가 방식

- **새로고침 후 스캔**

    | 항목 | 입력 | 기본값 | 예시 |
    | --- | --- | --- | --- |
    | 설명 | 선택 | 작업 이름 | VOD 드라마를 새로고침 후 스캔 |
    | 로컬 경로 | 선택 | / | /mnt/gds/VOD/1.방송중/드라마 |
    | 라이브러리 섹션 | 선택 | 선택 안 함 | 선택 안 함 |
    | VFS 리모트 | **필수** | 설정 메뉴의 `리모트` 값 | gds: |
    | recursive | 선택 | Off | Off |
    | 스캔 방식 | **필수** | Plexmate 스캔 | 주기적 스캔 |
    | 주기적 스캔 작업 | `주기적 스캔`일 경우 **필수** | 목록 | 1. 최신 드라마: 최신드라마 주기적 스캔 |
    | 일정 방식 | 선택 | 없음 | 시간 간격 |
    | 시간 간격 | `시간 간격`일 경우 **필수** | 60 | 10 5 * * * |
    | 시작시 일정 등록 | 선택 | Off | On |


- **새로고침**

    | 항목 | 입력 | 기본값 | 예시 |
    | --- | --- | --- | --- |
    | 설명 | 선택 | 작업 이름| VOD 예능을 새로고침 |
    | 로컬 경로 | 선택 | / | / |
    | 라이브러리 섹션 | 선택 | 선택 안 함 | 국내TV 예능 |
    | VFS 리모트 | **필수** | 설정 메뉴의 `리모트` 값 | gds: |
    | recursive | 선택 | Off | On |
    | 일정 방식 | 선택 | 없음 | 시간 간격 |
    | 시간 간격 | `시간 간격`일 경우 **필수** | 60 | 5 4 * * * |
    | 시작시 일정 등록 | 선택 | Off | On |


- **스캔**

    | 항목 | 입력 | 기본값 | 예시 |
    | --- | --- | --- | --- |
    | 설명 | 선택 | 작업 이름 | 드라마 폴더 스캔 |
    | 로컬 경로 | `주기적 스캔`일 경우 불필요 | / | |
    | 라이브러리 섹션 | `주기적 스캔`일 경우 불필요 | 선택 안 함 | 선택 안 함 |
    | 스캔 방식 | **필수** | Plexmate 스캔 | 주기적 스캔
    | 주기적 스캔 작업 | `주기적 스캔`일 경우 **필수** | 목록 | 2. 국내 드라마: 국내TV/드라마|
    | 일정 방식 | 선택 | 없음 | 시간 간격 |
    | 시간 간격 | `시간 간격`일 경우 **필수** | 60 | 10 4 * * * |
    | 시작시 일정 등록 | 선택 | Off | On |


- **Plexmate Ready 새로고침**

    | 항목 | 입력 | 기본값 | 예시 |
    | --- | --- | --- | --- |
    | 설명 | 선택 | 작업 이름 | plex_mate READY 항목을 새로고침 |
    | VFS 리모트 | **필수** | 설정 메뉴의 `리모트` 값  | gds: |
    | recursive | 선택 | Off | Off |
    | 일정 방식 | 선택 | 없음 | 시간 간격 |
    | 시간 간격 | `시간 간격`일 경우 **필수** | 60 | */10 * * * * |
    | 시작시 일정 등록 | 선택 | Off | On |


- **Plexmate 파일 정리**

    | 항목 | 입력 | 기본값 | 예시 |
    | --- | --- | --- | --- |
    | 설명 | 선택 | 작업 이름 | 최신 영화 섹션 파일 정리 |
    | 파일 정리 유형 | **필수** | 영화 | 영화 |
    | 파일 정리 단계 | **필수** | 1단계 | 2단계 |
    | 파일 정리 섹션 | **필수** | 목록 | 최신 영화 |
    | 일정 방식 | 선택 | 없음 | 시간 간격 |
    | 시간 간격 | `시간 간격`일 경우 **필수**| 60 | 10 6 * * * |
    | 시작시 일정 등록 | 선택 | Off | On |


- **시작 스크립트**

    | 항목 | 입력 | 기본값 | 예시 |
    | --- | --- | --- | --- |
    | 설명 | 선택 | 작업 이름 | FF 시작시 실행되는 스크립트 |
    | 일정 방식 | 고정 | 시작시 실행 | 시작시 실행 |


### 2. 일정 목록의 메뉴 버튼에서 해당 작업을 지금 실행

일정 목록의 우측에 위치한 메뉴 버튼을 클릭한 후 `지금 실행` 선택

<br />

### 3. 파일 탐색기의 우클릭 콘텍스트 메뉴로 실행

- 하단 간이 파일 탐색기에서 원하는 항목을 우클릭
- 우클릭 콘텍스트 메뉴에서 작업 선택
- `새로고침 후 스캔`, `새로고침`, `스캔`, `경로 캐시 삭제` 작업은 폴더에만 실행할 수 있습니다.
- `경로 캐시 삭제`는 Rclone 리모트 서버에 `vfs/forget` 명령을 보내 디렉토리 캐시에서 해당 경로의 캐시를 삭제합니다.


### 4. 도구

#### Plex 휴지통 스캔

플렉스 라이브러리에서 이용 불가로 표시되어 있는 미디어를 조회합니다. 조회되는 미디어의 폴더를 `새로고침`, `스캔`, `삭제`, `플렉스 휴지통 비우기` 합니다.

- 새로고침

    `새로고침`의 대상은 `스캔이 필요한 폴더`이며 `recursive`는 꺼진 상태로 동작합니다.

- 스캔

    `스캔`은 `Plex Web API`로 실행 됩니다. `새로고침`과 마찬가지로 `스캔이 필요한 폴더`만 부분 스캔이 실행됩니다.

- 비우기

    `비우기`는 Plex 서버에 현재 선택된 섹션의 `휴지통 비우기` 명령을 전송합니다.

- 새로고침 > 스캔

    단순히 `스캔이 필요한 폴더`들을 `새로고침` 후 `스캔` 합니다. 대상 폴더를 각각 `새로고침` 후 `스캔` 명령이 플렉스 서버에 전송되는 방식입니다.

- 새로고침 > 스캔 > 비우기

    `새로고침`과 `스캔` 이후에도 이용 불가로 표시되는 미디어가 있습니다. 그럴 경우 `휴지통 비우기`까지 한번에 처리하기 위한 옵션입니다. `휴지통 비우기`는 플랙스 서버의 `스캔` Activity가 종료될 때까지 대기 후 실행됩니다. 해당 라이브러리가 계속 `스캔` 상태일 경우 `휴지통 비우기`는 취소 됩니다.

- 삭제

    `비우기`로 전체 섹션의 이용 불가 미디어를 삭제하는 대신 특정 미디어만 `삭제`할 때 사용합니다. 이용 불가로 표시되는 미디어의 목록에서 각 항목의 우측 메뉴 버튼을 클릭하면 `삭제`를 실행할 수 있습니다. `삭제`는 플렉스 서버 옵션 중 `미디어 삭제 허용`이 체크되어 있어야 제대로 작동합니다.
