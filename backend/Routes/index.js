import express from 'express';
import userRouter from "./user.js";
import chatRouter from "./chat.js";
const router=express.Router();
router.use("/user",userRouter);
router.use("/chat",chatRouter);
export default router;