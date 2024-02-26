const E_SETTING_TEST_CONN = $('#btn_test_connection_rclone');
const E_SETTING_VFSES = $('#setting_rclone_remote_vfs');
const E_GDS_TOOL_REQUEST_SPAN = $('#setting_gds_tool_request_span');
const E_GDS_TOOL_REQUEST_AUTO = $('#setting_gds_tool_request_auto');
const E_GDS_TOOL_REQUEST_TOTAL = $('#setting_gds_tool_request_total');
const E_GDS_TOOL_REQUEST_DEL = $('#setting_gds_tool_request_del');
const E_GDS_TOOL_FP_SPAN = $('#setting_gds_tool_fp_span');
const E_GDS_TOOL_FP_AUTO = $('#setting_gds_tool_fp_auto');
const E_GDS_TOOL_FP_TOTAL = $('#setting_gds_tool_fp_total');
const E_GDS_TOOL_FP_DEL = $('#setting_gds_tool_fp_del');
const E_PLEXMATE_TIMEOVER_RANGE = $('#setting_plexmate_timeover_range');
const E_PLEXMATE_TIMEOVER_BTN = $('#setting_plexmate_timeover_btn');

function callback_test_connection(result) {
    if (result.ret == 'success') {
        E_SETTING_TEST_CONN.text('접속 성공');
        E_SETTING_VFSES.empty();
        result.vfses.forEach(function(vfs) {
            E_SETTING_VFSES.append($('<option></option>').prop('value', vfs).append(vfs));
        });
        E_SETTING_VFSES.prop('value', (VFS) ? VFS : result.vfses[0]);
    } else {
        console.log('Connection failed');
        console.log(result.ret);
        E_SETTING_TEST_CONN.text('접속 실패');
    }
}

E_SETTING_TEST_CONN.on('click', function (e) {
    globalSettingSave();
    e.preventDefault();
    globalSendCommand('command_test_connection', null, null, null, callback_test_connection);
});
E_GDS_TOOL_REQUEST_SPAN.prop('value', SETTING_GDS_TOOL_REQUEST_SPAN);
E_GDS_TOOL_REQUEST_AUTO.bootstrapToggle(SETTING_GDS_TOOL_REQUEST_AUTO ? 'on' : 'off');
E_GDS_TOOL_REQUEST_TOTAL.text(SETTING_GDS_TOOL_REQUEST_TOTAL);
E_GDS_TOOL_FP_SPAN.prop('value', SETTING_GDS_TOOL_FP_SPAN);
E_GDS_TOOL_FP_AUTO.bootstrapToggle(SETTING_GDS_TOOL_FP_AUTO ? 'on' : 'off');
E_GDS_TOOL_FP_TOTAL.text(SETTING_GDS_TOOL_FP_TOTAL);
E_GDS_TOOL_REQUEST_DEL.on('click', function(e) {
    span = E_GDS_TOOL_REQUEST_SPAN.prop('value');
    confirm_modal('복사 요청 목록을 삭제할까요?',
        '잔여 기간: ' + span,
        function() {
            globalSendCommandPage('clear_db', 'mod=request&span=' + span, null, null, null);
    });
});
E_GDS_TOOL_FP_DEL.on('click', function(e) {
    span = E_GDS_TOOL_FP_SPAN.prop('value');
    confirm_modal('변경사항 목록을 삭제할까요?',
        '잔여 기간: ' + span,
        function() {
            globalSendCommandPage('clear_db', 'mod=fp&span=' + span, null, null, null);
    });
});
E_PLEXMATE_TIMEOVER_BTN.on('click', function (e) {
    range = E_PLEXMATE_TIMEOVER_RANGE.prop('value');
    e.preventDefault();
    globalSendCommand('check_timeover', 'range=' + range, null, null, null);
});
