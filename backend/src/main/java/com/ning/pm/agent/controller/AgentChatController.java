package com.ning.pm.agent.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.agent.dto.AgentChatCommand;
import com.ning.pm.agent.service.AgentChatService;
import com.ning.pm.agent.vo.AgentChatVO;
import com.ning.pm.common.response.R;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * AgentChatController 提供 Agent 对话接口，
 * 仅接受最小必要参数，其余字段由服务端按业务策略自动组装。
 *
 * @author ning
 * @date 2026-06-15
 */
@SaCheckLogin
@RestController
@RequestMapping("/api/v1/agent")
public class AgentChatController {

    private static final Logger log = LoggerFactory.getLogger(AgentChatController.class);

    private final AgentChatService agentChatService;

    public AgentChatController(AgentChatService agentChatService) {
        this.agentChatService = agentChatService;
    }

    /** 发起一轮 Agent 对话。 */
    @PostMapping("/chat")
    public R<AgentChatVO> chat(@Valid @RequestBody AgentChatCommand command) {
        log.info("收到 Agent 对话请求 conversationId={} iterationId={} projectId={} taskId={}",
                command.conversationId(), command.iterationId(), command.projectId(), command.taskId());
        AgentChatVO result = agentChatService.chat(command);
        log.info("Agent 对话响应完成 conversationId={} turnIndex={} totalTokens={}",
                result.conversationId(), result.turnIndex(),
                result.usage() == null ? null : result.usage().totalTokens());
        return R.success(result);
    }
}
