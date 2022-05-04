//
// Autogenerated by Thrift Compiler (0.15.0)
//
// DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
//
"use strict";

var thrift = require('thrift');
var Thrift = thrift.Thrift;
var Q = thrift.Q;
var Int64 = require('node-int64');


var ttypes = module.exports = {};
ttypes.CodeChatClientLocation = {
  '0' : 'url',
  'url' : 0,
  '1' : 'html',
  'html' : 1,
  '2' : 'browser',
  'browser' : 2
};
var RenderClientReturn = module.exports.RenderClientReturn = function(args) {
  this.html = null;
  this.id = null;
  this.error = null;
  if (args) {
    if (args.html !== undefined && args.html !== null) {
      this.html = args.html;
    }
    if (args.id !== undefined && args.id !== null) {
      this.id = args.id;
    }
    if (args.error !== undefined && args.error !== null) {
      this.error = args.error;
    }
  }
};
RenderClientReturn.prototype = {};
RenderClientReturn.prototype.read = function(input) {
  input.readStructBegin();
  while (true) {
    var ret = input.readFieldBegin();
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid) {
      case 1:
      if (ftype == Thrift.Type.STRING) {
        this.html = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      case 2:
      if (ftype == Thrift.Type.I32) {
        this.id = input.readI32();
      } else {
        input.skip(ftype);
      }
      break;
      case 3:
      if (ftype == Thrift.Type.STRING) {
        this.error = input.readString();
      } else {
        input.skip(ftype);
      }
      break;
      default:
        input.skip(ftype);
    }
    input.readFieldEnd();
  }
  input.readStructEnd();
  return;
};

RenderClientReturn.prototype.write = function(output) {
  output.writeStructBegin('RenderClientReturn');
  if (this.html !== null && this.html !== undefined) {
    output.writeFieldBegin('html', Thrift.Type.STRING, 1);
    output.writeString(this.html);
    output.writeFieldEnd();
  }
  if (this.id !== null && this.id !== undefined) {
    output.writeFieldBegin('id', Thrift.Type.I32, 2);
    output.writeI32(this.id);
    output.writeFieldEnd();
  }
  if (this.error !== null && this.error !== undefined) {
    output.writeFieldBegin('error', Thrift.Type.STRING, 3);
    output.writeString(this.error);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

ttypes.THRIFT_PORT = 27376;