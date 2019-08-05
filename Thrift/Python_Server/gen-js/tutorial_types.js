//
// Autogenerated by Thrift Compiler (0.11.0)
//
// DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
//


get_result_type = {
  'html' : 0,
  'build' : 1,
  'status' : 2
};
get_result_return = function(args) {
  this.gr_type = null;
  this.text = null;
  if (args) {
    if (args.gr_type !== undefined && args.gr_type !== null) {
      this.gr_type = args.gr_type;
    }
    if (args.text !== undefined && args.text !== null) {
      this.text = args.text;
    }
  }
};
get_result_return.prototype = {};
get_result_return.prototype.read = function(input) {
  input.readStructBegin();
  while (true)
  {
    var ret = input.readFieldBegin();
    var fname = ret.fname;
    var ftype = ret.ftype;
    var fid = ret.fid;
    if (ftype == Thrift.Type.STOP) {
      break;
    }
    switch (fid)
    {
      case 1:
      if (ftype == Thrift.Type.I32) {
        this.gr_type = input.readI32().value;
      } else {
        input.skip(ftype);
      }
      break;
      case 2:
      if (ftype == Thrift.Type.STRING) {
        this.text = input.readString().value;
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

get_result_return.prototype.write = function(output) {
  output.writeStructBegin('get_result_return');
  if (this.gr_type !== null && this.gr_type !== undefined) {
    output.writeFieldBegin('gr_type', Thrift.Type.I32, 1);
    output.writeI32(this.gr_type);
    output.writeFieldEnd();
  }
  if (this.text !== null && this.text !== undefined) {
    output.writeFieldBegin('text', Thrift.Type.STRING, 2);
    output.writeString(this.text);
    output.writeFieldEnd();
  }
  output.writeFieldStop();
  output.writeStructEnd();
  return;
};

