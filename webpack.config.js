const path = require('path');

module.exports = {
    resolve: {
        alias: {
            '@product_connect': path.resolve(__dirname, 'static/src'),
            '@product_connect/tests': path.resolve(__dirname, 'static/tests'),
        },
        extensions: ['.js'],
    },
};
