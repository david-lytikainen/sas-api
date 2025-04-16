#!/bin/bash
cd "$(dirname "$0")/../../sas-ui/client"
export PORT=3000
npm install
npm start
