SOCKET.on('result', function(data) {
    console.log(data);
});

globalSendCommandPage('test', null, null, null, null);
