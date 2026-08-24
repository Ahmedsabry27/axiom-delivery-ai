export type DeliveryDataMode="api"|"mock";

export type DeliveryDataEnvironment={
  production:boolean;
  mode:string;
};

export function parseDeliveryDataMode(raw:string|undefined,environment:DeliveryDataEnvironment):DeliveryDataMode{
  if(raw===undefined||raw===""||raw==="false")return "api";
  if(raw!=="true")throw new Error("VITE_USE_MOCK_DELIVERY_DATA must be either 'true' or 'false'.");
  if(environment.production||environment.mode==="production")throw new Error("Delivery mock data is forbidden in production builds.");
  if(!["development","test"].includes(environment.mode))throw new Error(`Delivery mock data is not supported in ${environment.mode||"unknown"} mode.`);
  return "mock";
}

export const deliveryDataMode=parseDeliveryDataMode(import.meta.env.VITE_USE_MOCK_DELIVERY_DATA,{production:import.meta.env.PROD,mode:import.meta.env.MODE});
export const isDeliveryMockMode=()=>deliveryDataMode==="mock";
