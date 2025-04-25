const path = require('path');

module.exports = {
    resolve: {
        alias: {
            '@odoo/owl': path.resolve(__dirname, 'odoo/addons/web/static/lib/owl'),
            '@web': path.resolve(__dirname, 'odoo/addons/web/static'),
            '@product_connect': path.resolve(__dirname, 'addons/product_connect/static/src'),
        },
        extensions: ['.js'],
    },
};
