"""csi/common — web(FastAPI) 과 GUI(PyQt) 가 공유하는 디바이스 I/O 백엔드.

UI 프레임워크와 무관한 로직(보드 실시간 감지, role 자동감지, 펌웨어 flash,
CSI 진폭/위상 스트림, 포트 직렬화 락)을 모아 둔다. web 은 WebSocket, GUI 는
QThread 시그널로 이 모듈들을 동일하게 호출한다.
"""
