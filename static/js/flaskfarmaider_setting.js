const E_SETTING_TEST_CONN = $('#btn_test_connection_rclone');
const E_SETTING_VFSES = $('#setting_rclone_remote_vfs');
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
    globalSendCommand('test_conn', null, null, null, callback_test_connection);
});
E_PLEXMATE_TIMEOVER_BTN.on('click', function (e) {
    range = E_PLEXMATE_TIMEOVER_RANGE.prop('value');
    e.preventDefault();
    globalSendCommand('check_timeover', 'range=' + range, null, null, null);
});
