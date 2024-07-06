const E_SETTING_TEST_CONN = $('#btn_test_connection_rclone');
const E_SETTING_VFSES = $('#setting_rclone_remote_vfs');
const E_PLEXMATE_TIMEOVER_RANGE = $('#setting_plexmate_timeover_range');
const E_PLEXMATE_TIMEOVER_BTN = $('#setting_plexmate_timeover_btn');

function testConnection() {
    let thisButton = $(this);
    globalSendCommand('test_connection', thisButton.prev('input').prop('value'), null, null, function(result) {
        switch (result.ret) {
            case 'success':
                thisButton.prop('innerHTML', '접속 성공');
                break;
            default:
                thisButton.prop('innerHTML', '접속 실패');
        }
    });
}

function saveSettings() {
    // model_setting.py의 setting_save()에서 중복 name을 처리 못 함.
    globalSettingSaveBefore();
    let formdata = getFormdata('#setting');;
    formdata += '&command=save_settings';
    $.ajax({
        url: '/' + PACKAGE_NAME + '/ajax/' + MODULE_NAME + '/command',
        type: "POST",
        cache: false,
        data: formdata,
        dataType: "json",
        success: function(result) {
            notify(result.msg, result.ret)
            if (result.ret == 'success') {
                globalSettingSaveAfter();
            }
        }
    });
}

function renderRemoteGroup() {
    const E_RCLONE_REMOTE_GROUP = $('#rclone-remote-group');
    let defaultInputGroup = '<div class="input-group">';
    defaultInputGroup += '<input name="setting_rclone_remotes" class="form-control form-control-sm" type="text" placeholder="http://172.17.0.1:5572">'
    defaultInputGroup += '<button type="button" class="btn btn-outline-primary btn-sm btn-test-connection">접속 확인</button>';
    defaultInputGroup += '<button type="button" class="btn btn-outline-warning btn-sm btn-remove-remote">삭제</button>';
    defaultInputGroup += '</div>';
    for (let idx in SETTING_RCLONE_REMOTES) {
        let inputGroup = $(defaultInputGroup);
        if (idx < 1) {
            inputGroup.children('.btn-remove-remote').remove();
            inputGroup.append('<button type="button" class="btn btn-outline-primary btn-sm btn-add-remote">추가</button>');
        }
        inputGroup.children('input').prop('value', SETTING_RCLONE_REMOTES[idx]);
        inputGroup.on('click', '.btn-test-connection', testConnection);
        inputGroup.on('click', '.btn-add-remote', function() {
            let addingInputGroup = $(defaultInputGroup);
            addingInputGroup.on('click', '.btn-test-connection', testConnection);
            addingInputGroup.on('click', '.btn-remove-remote', function() {
                $(this).parent().remove();
            });
            E_RCLONE_REMOTE_GROUP.append(addingInputGroup);
        });
        inputGroup.on('click', '.btn-remove-remote', function() {
            $(this).parent().remove();
        });
        E_RCLONE_REMOTE_GROUP.append(inputGroup);
    }
}

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

renderRemoteGroup();
renderAddableInputGroup(SETTING_RCLONE_MAPPINGS, 'rclone-mapping-group', 'setting_rclone_mappings', '/mnt/gds/GDRIVE:/GDRIVE');
renderAddableInputGroup(SETTING_PLEX_MAPPINGS, 'plex-mapping-group', 'setting_plex_mappings', '/mnt/gds/GDRIVE:/host/mnt/gds/GDRIVE');
renderAddableInputGroup(SETTING_STARTUP_COMMANDS, 'startup-command-group', 'setting_startup_commands', 'apt-get update');

$('#btn-save-settings').on('click', saveSettings);

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

$('#setting_startup_executable').bootstrapToggle((SETTING_STARTUP_EXECUTABLE ? 'on' : 'off'));
$('#setting_logging_login').bootstrapToggle((SETTING_LOGGING_LOGIN ? 'on' : 'off'));
$('#setting_logging_access').bootstrapToggle((SETTING_LOGGING_ACCESS ? 'on' : 'off'));

$('#setting_startup_dependencies_update_Btn').on('click', function() {
    $(this);
    confirmModal(
        '최신 내용으로 덮어쓸까요?',
        '<a href="https://raw.githubusercontent.com/halfaider/flaskfarmaider/main/files/flaskfarmaider.yaml" target=_blank>https://raw.githubusercontent.com/halfaider/flaskfarmaider/main/files/flaskfarmaider.yaml</a>',
        function() {
            globalSendCommand('update_dependencies', null, null, null, null);
        }
    );
});