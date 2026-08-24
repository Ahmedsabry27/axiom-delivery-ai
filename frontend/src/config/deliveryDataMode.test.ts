import {describe,expect,it} from "vitest";
import {parseDeliveryDataMode} from "./deliveryDataMode";

describe("delivery data mode",()=>{
  it.each([undefined,"","false"])("uses the API when the value is %s",value=>{
    expect(parseDeliveryDataMode(value,{production:false,mode:"development"})).toBe("api");
  });
  it("allows explicitly enabled mocks in development and test",()=>{
    expect(parseDeliveryDataMode("true",{production:false,mode:"development"})).toBe("mock");
    expect(parseDeliveryDataMode("true",{production:false,mode:"test"})).toBe("mock");
  });
  it("rejects mocks in production and preview modes",()=>{
    expect(()=>parseDeliveryDataMode("true",{production:true,mode:"production"})).toThrow(/forbidden/i);
    expect(()=>parseDeliveryDataMode("true",{production:false,mode:"preview"})).toThrow(/not supported/i);
  });
  it("rejects invalid values",()=>expect(()=>parseDeliveryDataMode("yes",{production:false,mode:"development"})).toThrow(/true.*false/i));
});
